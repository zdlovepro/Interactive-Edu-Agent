from __future__ import annotations

from urllib.parse import parse_qs, urlencode

from .config import DEFAULT_COURSE_QUERY_SUFFIX, DEFAULT_COURSE_URL_BASE, validate_chaoxing_url
from .errors import InvalidCourseRefError
from .models import ChaoxingCourseRef


def parse_chaoxing_course_url(url: str) -> ChaoxingCourseRef:
    parsed = validate_chaoxing_url(url)
    query = parse_qs(parsed.query, keep_blank_values=True)

    courseid = _get_single_query_value(query, "courseid")
    if not courseid:
        raise InvalidCourseRefError("Chaoxing course URL must include a non-empty courseid.")

    return ChaoxingCourseRef(
        courseid=courseid,
        clazzid=_get_single_query_value(query, "clazzid"),
        cpi=_get_single_query_value(query, "cpi"),
        enc=_get_single_query_value(query, "enc"),
        raw_url=url,
        referer=url,
    )


def build_chaoxing_course_url(ref: ChaoxingCourseRef) -> str:
    if ref.raw_url:
        validate_chaoxing_url(ref.raw_url)
        return ref.raw_url

    if not ref.courseid:
        raise InvalidCourseRefError("courseid is required to build a Chaoxing course URL.")

    query_items: list[tuple[str, str]] = [("courseid", ref.courseid)]
    if ref.clazzid:
        query_items.append(("clazzid", ref.clazzid))
    if ref.cpi:
        query_items.append(("cpi", ref.cpi))
    if ref.enc:
        query_items.append(("enc", ref.enc))
    query_items.extend(DEFAULT_COURSE_QUERY_SUFFIX)

    return f"{DEFAULT_COURSE_URL_BASE}?{urlencode(query_items)}"


def _get_single_query_value(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    if not values:
        return None

    value = values[0].strip()
    return value or None
