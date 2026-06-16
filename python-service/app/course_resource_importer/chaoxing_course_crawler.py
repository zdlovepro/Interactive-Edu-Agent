from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qs, quote, urlencode, urlsplit

import aiohttp

from app.core.config import settings
from app.utils.logger import logger

from .authorized_fetcher import fetch_authorized_html, fetch_authorized_html_with_final_url
from .config import DEFAULT_RATE_LIMIT_PER_HOST, DEFAULT_TIMEOUT_SECONDS, DEFAULT_USER_AGENT, validate_chaoxing_url
from .json_resource_discoverer import discover_resources_from_json
from .models import AuthorizedFetchContext, ChaoxingCourseRef
from .resource_models import DiscoveredResource, dedupe_discovered_resources

_MOOC1 = "https://mooc1.chaoxing.com"
_MOOC2 = "https://mooc2-ans.chaoxing.com"
_INPUT_RE = re.compile(r"<input\b[^>]*\bname=['\"](?P<name>[^'\"]+)['\"][^>]*\bvalue=['\"](?P<value>[^'\"]*)['\"]", re.I)
_ENC_RE = re.compile(r"var\s+enc\s*=\s*['\"](?P<enc>[^'\"]+)['\"]\s*;", re.I)
_TO_OLD_RE = re.compile(r"toOld\(['\"](?P<courseid>[^'\"]+)['\"]\s*,\s*['\"](?P<knowledgeid>[^'\"]+)['\"]\s*,\s*['\"](?P<clazzid>[^'\"]+)['\"]\)", re.I)
_CARD_COUNT_RE = re.compile(r"id=['\"]cardcount['\"][^>]*value=['\"](?P<count>\d+)['\"]", re.I)
_MARG_RE = re.compile(r"mArg\s*=\s*(?P<payload>\{[\s\S]*?\})\s*;?\s*\}?\s*catch", re.I)
_MARG_FALLBACK_RE = re.compile(r"mArg\s*=\s*(?P<payload>\{[\s\S]*?\})\s*;", re.I)
_RESOURCE_TYPES = {"document", "insertimage", "ppt", "pdf"}


@dataclass(slots=True)
class _ChapterRef:
    courseid: str
    clazzid: str
    knowledgeid: str
    transfer_url: str
    title: str | None = None


async def discover_resources_from_chaoxing_course_structure(
    *,
    course_ref: ChaoxingCourseRef,
    page_url: str,
    page_html: str,
    context: AuthorizedFetchContext,
) -> list[DiscoveredResource]:
    """Discover resources from Chaoxing chapter/card attachment metadata.

    This is a read-only subset inspired by the earlier local Chaoxing helper: it only follows URLs and
    object IDs that already appear in the user's authorized course pages.
    """

    try:
        validate_chaoxing_url(page_url)
        course_info = _extract_course_info(course_ref, page_html)
        if not course_info.get("courseid") or not course_info.get("clazzid") or not course_info.get("cpi"):
            logger.info("Chaoxing structured discovery skipped because courseid/clazzid/cpi are incomplete.")
            return []

        studentcourse_url = _studentcourse_url(course_info)
        studentcourse_html = await fetch_authorized_html(studentcourse_url, _with_referer(context, page_url))
        enc = course_info.get("enc") or _extract_enc(studentcourse_html)
        chapters = _extract_chapters(studentcourse_html, enc=enc)
        if not chapters:
            logger.info("Chaoxing structured discovery found no chapters. courseid=%s", course_info.get("courseid"))
            return []

        resources: list[DiscoveredResource] = []
        for chapter in chapters[: settings.CHAOXING_MAX_CHAPTERS]:
            try:
                resources.extend(await _discover_from_chapter(chapter, cpi=str(course_info["cpi"]), context=context))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Chaoxing chapter discovery skipped. chapterId=%s reason=%s", chapter.knowledgeid, exc)

        return dedupe_discovered_resources(resources)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chaoxing structured discovery skipped. courseid=%s reason=%s", course_ref.courseid, exc)
        return []


async def _discover_from_chapter(
    chapter: _ChapterRef,
    *,
    cpi: str,
    context: AuthorizedFetchContext,
) -> list[DiscoveredResource]:
    resources: list[DiscoveredResource] = []
    chapter_page = await fetch_authorized_html_with_final_url(
        chapter.transfer_url,
        _with_referer(context, f"{_MOOC2}/"),
    )
    chapter_referrer = chapter_page.final_url or chapter.transfer_url
    chapter_cpi = _query_value(chapter_referrer, "cpi") or cpi
    card_count = await _read_card_count(chapter, cpi=chapter_cpi, referer=chapter_referrer, context=context)

    for card_index in range(min(card_count, settings.CHAOXING_MAX_CARDS_PER_CHAPTER)):
        cards_url = (
            f"{_MOOC1}/knowledge/cards?"
            + urlencode(
                {
                    "clazzid": chapter.clazzid,
                    "courseid": chapter.courseid,
                    "knowledgeid": chapter.knowledgeid,
                    "num": str(card_index),
                    "ut": "s",
                    "cpi": chapter_cpi,
                    "v": "20160407-1",
                }
            )
        )
        cards_html = await fetch_authorized_html(cards_url, _with_referer(context, chapter_referrer))
        card_args = _extract_marg(cards_html)
        if not card_args:
            continue
        resources.extend(
            discover_resources_from_json(
                card_args,
                source_url=cards_url,
                course_ref=_course_ref_from_chapter(chapter, chapter_cpi, referer=chapter_referrer),
            )
        )
        resources.extend(
            await _discover_attachment_statuses(
                card_args,
                cards_url=cards_url,
                chapter=chapter,
                context=context,
                referer=chapter_referrer,
            )
        )

    _ = chapter_page.html  # Kept for future page-level discovery without changing behavior.
    return dedupe_discovered_resources(resources)


async def _read_card_count(
    chapter: _ChapterRef,
    *,
    cpi: str,
    referer: str,
    context: AuthorizedFetchContext,
) -> int:
    url = f"{_MOOC1}/mycourse/studentstudyAjax"
    body = urlencode(
        {
            "courseId": chapter.courseid,
            "clazzid": chapter.clazzid,
            "chapterId": chapter.knowledgeid,
            "cpi": cpi,
            "verificationcode": "",
            "mooc2": "1",
        }
    )
    text = await _post_chaoxing_form(url, body=body, context=_with_referer(context, referer))
    match = _CARD_COUNT_RE.search(text)
    if not match:
        return 0
    return int(match.group("count"))


async def _discover_attachment_statuses(
    card_args: dict,
    *,
    cards_url: str,
    chapter: _ChapterRef,
    context: AuthorizedFetchContext,
    referer: str,
) -> list[DiscoveredResource]:
    attachments = card_args.get("attachments")
    if not isinstance(attachments, list):
        return []

    resources: list[DiscoveredResource] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        attachment_type = str(attachment.get("type") or "").strip().lower()
        if attachment_type and attachment_type not in _RESOURCE_TYPES:
            continue

        prop = attachment.get("property") if isinstance(attachment.get("property"), dict) else {}
        object_id = prop.get("objectid") or prop.get("objectId") or attachment.get("objectid") or attachment.get("objectId")
        if not object_id:
            continue

        status_url = f"{_MOOC1}/ananas/status/{object_id}?flag=normal&_dc={int(time.time() * 1000)}"
        try:
            status_text = await fetch_authorized_html(
                status_url,
                _with_referer(context, f"{_MOOC1}/ananas/modules/pdf/index.html?v=2022-0830-1135"),
            )
            status_json = json.loads(status_text)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Chaoxing attachment status skipped. objectId=%s reason=%s", object_id, exc)
            continue

        if isinstance(status_json, dict):
            status_json.setdefault("objectid", object_id)
            status_json.setdefault("name", prop.get("name") or prop.get("title"))
            status_json.setdefault("chapterId", chapter.knowledgeid)
            resources.extend(discover_resources_from_json(status_json, source_url=cards_url, course_ref=_course_ref_from_chapter(chapter, None, referer=referer)))

    return resources


async def _post_chaoxing_form(url: str, *, body: str, context: AuthorizedFetchContext) -> str:
    validate_chaoxing_url(url)
    headers = {
        "User-Agent": context.user_agent,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": _MOOC1,
    }
    if context.cookie:
        headers["Cookie"] = context.cookie
    if context.authorization:
        headers["Authorization"] = context.authorization
    if context.referer:
        headers["Referer"] = context.referer

    await asyncio.sleep(max(0.0, 1.0 / DEFAULT_RATE_LIMIT_PER_HOST))
    timeout = aiohttp.ClientTimeout(total=context.timeout_seconds or DEFAULT_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout, trust_env=False) as session:
        async with session.post(url, data=body, headers=headers, allow_redirects=True) as response:
            text = await response.text(errors="replace")
            if response.status >= 400:
                raise RuntimeError(f"Chaoxing form request failed with status {response.status}")
            return text


def _extract_course_info(course_ref: ChaoxingCourseRef, page_html: str) -> dict[str, str | None]:
    inputs: dict[str, str] = {}
    for match in _INPUT_RE.finditer(page_html or ""):
        inputs[match.group("name").lower()] = unescape(match.group("value"))

    return {
        "courseid": course_ref.courseid or inputs.get("courseid"),
        "clazzid": course_ref.clazzid or inputs.get("clazzid"),
        "cpi": course_ref.cpi or inputs.get("cpi"),
        "enc": course_ref.enc or inputs.get("enc"),
    }


def _extract_enc(studentcourse_html: str) -> str | None:
    match = _ENC_RE.search(studentcourse_html or "")
    return match.group("enc") if match else None


def _extract_chapters(studentcourse_html: str, *, enc: str | None) -> list[_ChapterRef]:
    chapters: list[_ChapterRef] = []
    for match in _TO_OLD_RE.finditer(studentcourse_html or ""):
        courseid = match.group("courseid")
        knowledgeid = match.group("knowledgeid")
        clazzid = match.group("clazzid")
        refer_url = (
            f"{_MOOC1}/mycourse/studentstudy?"
            + urlencode(
                {
                    "chapterId": knowledgeid,
                    "courseId": courseid,
                    "clazzid": clazzid,
                    "enc": enc or "",
                    "mooc2": "1",
                }
            )
        )
        transfer_url = f"{_MOOC1}/mycourse/transfer?moocId={courseid}&clazzid={clazzid}&ut=s&refer={quote(refer_url)}"
        chapters.append(_ChapterRef(courseid=courseid, clazzid=clazzid, knowledgeid=knowledgeid, transfer_url=transfer_url))
    return chapters


def _extract_marg(cards_html: str) -> dict | None:
    for pattern in (_MARG_RE, _MARG_FALLBACK_RE):
        match = pattern.search(cards_html or "")
        if not match:
            continue
        candidate = match.group("payload").strip()
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            continue
    return None


def _studentcourse_url(course_info: dict[str, str | None]) -> str:
    return (
        f"{_MOOC2}/mycourse/studentcourse?"
        + urlencode(
            {
                "courseid": str(course_info["courseid"]),
                "clazzid": str(course_info["clazzid"]),
                "cpi": str(course_info["cpi"]),
                "ut": "s",
            }
        )
    )


def _query_value(url: str, name: str) -> str | None:
    values = parse_qs(urlsplit(url).query).get(name)
    if not values:
        return None
    value = values[0].strip()
    return value or None


def _with_referer(context: AuthorizedFetchContext, referer: str | None) -> AuthorizedFetchContext:
    return AuthorizedFetchContext(
        cookie=context.cookie,
        authorization=context.authorization,
        referer=referer or context.referer,
        user_agent=context.user_agent or DEFAULT_USER_AGENT,
        timeout_seconds=context.timeout_seconds,
        rate_limit_per_host=context.rate_limit_per_host,
    )


def _course_ref_from_chapter(chapter: _ChapterRef, cpi: str | None, *, referer: str | None = None) -> ChaoxingCourseRef:
    return ChaoxingCourseRef(courseid=chapter.courseid, clazzid=chapter.clazzid, cpi=cpi, referer=referer or chapter.transfer_url)
