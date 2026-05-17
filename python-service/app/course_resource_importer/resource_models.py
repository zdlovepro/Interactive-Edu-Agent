from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath
from typing import Literal
from urllib.parse import parse_qs, unquote, urlsplit

from .models import ChaoxingCourseRef

SourceType = Literal["html", "json", "js", "api"]
ResourceKind = Literal[
    "slide_image",
    "courseware_file",
    "attachment",
    "content_image",
    "metadata",
    "ui_asset",
    "unknown",
]

COURSEWARE_EXTENSIONS = frozenset({"pdf", "ppt", "pptx"})
ATTACHMENT_EXTENSIONS = frozenset({"doc", "docx", "xls", "xlsx", "txt", "md"})
IMAGE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "webp"})
STATIC_ASSET_EXTENSIONS = frozenset({"js", "css"})
UI_ASSET_KEYWORDS = (
    "icon",
    "logo",
    "avatar",
    "button",
    "toolbar",
    "loading",
    "assistant",
    "translate",
    "speaker",
    "voice",
    "baguettebox",
    "aplus_queue",
    "sprite",
    "background",
    "read-loading",
)
SLIDE_IMAGE_KEYWORDS = (
    "slide",
    "page",
    "preview",
    "cover",
    "ppt",
    "courseware",
)


@dataclass(slots=True)
class DiscoveredResource:
    resource_id: str
    platform: str = "chaoxing"
    source_type: SourceType = "html"
    source_url: str | None = None
    url: str = ""
    title: str | None = None
    file_name: str = ""
    extension: str = ""
    mime_type: str | None = None
    courseid: str | None = None
    clazzid: str | None = None
    chapter_id: str | None = None
    object_id: str | None = None
    expected_size: int | None = None
    expected_md5: str | None = None
    resource_kind: ResourceKind = "unknown"
    confidence: float = 0.0
    reason: str = ""
    raw_context: dict = field(default_factory=dict)


def build_discovered_resource(
    *,
    url: str,
    source_type: SourceType,
    source_url: str | None = None,
    course_ref: ChaoxingCourseRef | None = None,
    title: str | None = None,
    file_name: str | None = None,
    extension: str | None = None,
    mime_type: str | None = None,
    courseid: str | None = None,
    clazzid: str | None = None,
    chapter_id: str | None = None,
    object_id: str | None = None,
    external_resource_id: str | None = None,
    expected_size: int | None = None,
    expected_md5: str | None = None,
    raw_context: dict | None = None,
) -> DiscoveredResource | None:
    context = dict(raw_context or {})
    resolved_file_name, resolved_extension = _resolve_file_name_and_extension(
        url=url,
        file_name=file_name,
        extension=extension,
        context=context,
    )

    if resolved_extension in STATIC_ASSET_EXTENSIONS:
        return None

    resolved_mime_type = mime_type or _guess_mime_type(resolved_file_name)
    resource_kind, confidence, reason = _classify_resource(
        url=url,
        file_name=resolved_file_name,
        extension=resolved_extension,
        title=title,
        context=context,
    )

    resolved_courseid = courseid or context.get("courseid") or (course_ref.courseid if course_ref else None)
    resolved_clazzid = clazzid or context.get("clazzid") or (course_ref.clazzid if course_ref else None)
    resolved_chapter_id = chapter_id or context.get("chapter_id") or context.get("chapterId")
    resolved_object_id = object_id or context.get("object_id") or context.get("objectid") or context.get("objectId")
    resolved_size = _coerce_int(expected_size if expected_size is not None else context.get("size"))
    resolved_md5 = (expected_md5 or context.get("md5") or context.get("expected_md5") or None)
    normalized_md5 = str(resolved_md5).strip().lower() if resolved_md5 else None

    resource_id = _build_resource_id(url, resolved_object_id, external_resource_id)
    if not resolved_file_name:
        resolved_file_name = _fallback_file_name(resolved_extension, resource_id)

    return DiscoveredResource(
        resource_id=resource_id,
        source_type=source_type,
        source_url=source_url,
        url=url,
        title=title,
        file_name=resolved_file_name,
        extension=resolved_extension,
        mime_type=resolved_mime_type,
        courseid=resolved_courseid,
        clazzid=resolved_clazzid,
        chapter_id=resolved_chapter_id,
        object_id=resolved_object_id,
        expected_size=resolved_size,
        expected_md5=normalized_md5,
        resource_kind=resource_kind,
        confidence=confidence,
        reason=reason,
        raw_context=context,
    )


def dedupe_discovered_resources(resources: list[DiscoveredResource]) -> list[DiscoveredResource]:
    deduped: list[DiscoveredResource] = []
    key_to_index: dict[str, int] = {}

    for resource in resources:
        keys = _resource_dedupe_keys(resource)
        existing_index = next((key_to_index[key] for key in keys if key in key_to_index), None)
        if existing_index is None:
            deduped.append(resource)
            index = len(deduped) - 1
            for key in keys:
                key_to_index[key] = index
            continue

        kept = deduped[existing_index]
        merged = _choose_preferred_resource(kept, resource)
        deduped[existing_index] = merged
        for key in _resource_dedupe_keys(merged):
            key_to_index[key] = existing_index

    return deduped


def _choose_preferred_resource(left: DiscoveredResource, right: DiscoveredResource) -> DiscoveredResource:
    if _resource_score(right) > _resource_score(left):
        merged_context = dict(left.raw_context)
        merged_context.update(right.raw_context)
        return replace(right, raw_context=merged_context)

    merged_context = dict(right.raw_context)
    merged_context.update(left.raw_context)
    return replace(left, raw_context=merged_context)


def _resource_score(resource: DiscoveredResource) -> tuple[int, int, float]:
    priority = {
        "courseware_file": 5,
        "attachment": 4,
        "slide_image": 3,
        "content_image": 2,
        "unknown": 1,
        "ui_asset": 0,
        "metadata": 0,
    }
    return (priority.get(resource.resource_kind, 0), len(resource.reason), resource.confidence)


def _resource_dedupe_keys(resource: DiscoveredResource) -> list[str]:
    keys = [f"url:{resource.url}", f"resource:{resource.resource_id}"]
    if resource.object_id:
        keys.append(f"object:{resource.object_id}")
    return keys


def _build_resource_id(url: str, object_id: str | None, external_resource_id: str | None) -> str:
    if external_resource_id:
        return f"resource:{str(external_resource_id).strip()}"
    if object_id:
        return f"object:{str(object_id).strip()}"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return f"url:{digest}"


def _resolve_file_name_and_extension(
    *,
    url: str,
    file_name: str | None,
    extension: str | None,
    context: dict,
) -> tuple[str, str]:
    parsed = urlsplit(url)
    path_name = PurePosixPath(unquote(parsed.path)).name
    query = parse_qs(parsed.query)

    resolved_file_name = (file_name or context.get("file_name") or context.get("fileName") or "").strip()
    if not resolved_file_name:
        resolved_file_name = (
            path_name
            or _first_query_value(query, "filename")
            or _first_query_value(query, "fileName")
            or _first_query_value(query, "name")
            or _first_query_value(query, "title")
            or str(context.get("name") or context.get("title") or "").strip()
        )

    resolved_extension = (extension or context.get("suffix") or context.get("type") or "").strip().lower().lstrip(".")
    if not resolved_extension and resolved_file_name:
        suffix = PurePosixPath(resolved_file_name).suffix.lower().lstrip(".")
        resolved_extension = suffix
    if not resolved_extension and path_name:
        resolved_extension = PurePosixPath(path_name).suffix.lower().lstrip(".")

    if resolved_file_name and resolved_extension and "." not in PurePosixPath(resolved_file_name).name:
        resolved_file_name = f"{resolved_file_name}.{resolved_extension}"

    return resolved_file_name, resolved_extension


def _classify_resource(
    *,
    url: str,
    file_name: str,
    extension: str,
    title: str | None,
    context: dict,
) -> tuple[ResourceKind, float, str]:
    lowered_haystack = " ".join(
        str(part or "").lower()
        for part in (
            url,
            file_name,
            title,
            context.get("class"),
            context.get("id"),
            context.get("attr_name"),
            context.get("source_field"),
        )
    )

    if extension in COURSEWARE_EXTENSIONS:
        return "courseware_file", 0.98, f"Matched courseware file extension .{extension}."
    if extension in ATTACHMENT_EXTENSIONS:
        return "attachment", 0.92, f"Matched attachment extension .{extension}."
    if extension in IMAGE_EXTENSIONS:
        if _looks_like_ui_asset(lowered_haystack, context):
            return "ui_asset", 0.12, "Image matched UI/static-asset heuristics."
        if _looks_like_slide_image(lowered_haystack):
            return "slide_image", 0.86, "Image matched slide/page preview heuristics."
        return "content_image", 0.74, "Image extension suggests course content imagery."
    if extension == "gif":
        if _looks_like_ui_asset(lowered_haystack, context):
            return "ui_asset", 0.08, "GIF matched loading/UI heuristics."
        return "unknown", 0.2, "GIF is not treated as a primary courseware resource."
    if not extension:
        return "unknown", 0.2, "URL did not expose a recognized file extension."
    return "unknown", 0.15, f"Extension .{extension} is not a targeted courseware type."


def _looks_like_ui_asset(lowered_haystack: str, context: dict) -> bool:
    if any(keyword in lowered_haystack for keyword in UI_ASSET_KEYWORDS):
        return True

    width = _coerce_int(context.get("width"))
    height = _coerce_int(context.get("height"))
    if width is not None and height is not None and width <= 128 and height <= 128:
        return True

    return False


def _looks_like_slide_image(lowered_haystack: str) -> bool:
    return any(keyword in lowered_haystack for keyword in SLIDE_IMAGE_KEYWORDS)


def _guess_mime_type(file_name: str) -> str | None:
    if not file_name:
        return None
    guessed, _ = mimetypes.guess_type(file_name)
    return guessed


def _fallback_file_name(extension: str, resource_id: str) -> str:
    if extension:
        return f"{resource_id}.{extension}"
    return resource_id


def _first_query_value(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key)
    if not values:
        return ""
    return str(values[0]).strip()


def _coerce_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
