from __future__ import annotations

import json
from collections.abc import Mapping

from .models import ChaoxingCourseRef
from .resource_models import DiscoveredResource, build_discovered_resource, dedupe_discovered_resources
from .url_utils import normalize_and_validate_resource_url

URL_FIELDS = frozenset(
    {
        "download",
        "downloadUrl",
        "objectUrl",
        "fileUrl",
        "url",
        "pdf",
        "ppt",
        "pptx",
        "pptUrl",
        "pdfUrl",
        "previewUrl",
        "resourceUrl",
    }
)
TITLE_FIELDS = ("title", "name", "fileName")
RESOURCE_ID_FIELDS = ("resourceId", "attachmentId", "fileId")
OBJECT_ID_FIELDS = ("objectid", "objectId")
SIZE_FIELDS = ("size",)
MD5_FIELDS = ("md5",)
CHAPTER_ID_FIELDS = ("chapterId", "chapter_id")
JSON_CONTAINER_FIELDS = ("fileinfo", "attachments", "attachment", "files")


def discover_resources_from_json(
    data: dict | list,
    source_url: str | None = None,
    course_ref: ChaoxingCourseRef | None = None,
) -> list[DiscoveredResource]:
    resources: list[DiscoveredResource] = []
    _walk_json_node(data, resources, source_url=source_url, course_ref=course_ref, inherited_context={})
    return dedupe_discovered_resources(resources)


def discover_resources_from_json_text(
    text: str,
    source_url: str | None = None,
    course_ref: ChaoxingCourseRef | None = None,
) -> list[DiscoveredResource]:
    parsed = try_parse_json_text(text)
    if parsed is None or not isinstance(parsed, (dict, list)):
        return []
    return discover_resources_from_json(parsed, source_url=source_url, course_ref=course_ref)


def try_parse_json_text(text: str) -> dict | list | None:
    candidate = str(text or "").strip()
    if not candidate or candidate[0] not in "[{":
        return None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def _walk_json_node(
    node: object,
    resources: list[DiscoveredResource],
    *,
    source_url: str | None,
    course_ref: ChaoxingCourseRef | None,
    inherited_context: dict,
) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_json_node(
                item,
                resources,
                source_url=source_url,
                course_ref=course_ref,
                inherited_context=inherited_context,
            )
        return

    if not isinstance(node, Mapping):
        return

    current_context = dict(inherited_context)
    current_context.update(_extract_context_from_mapping(node))

    for field_name in URL_FIELDS:
        value = node.get(field_name)
        if isinstance(value, str):
            normalized_url = normalize_and_validate_resource_url(value, base_url=source_url)
            if not normalized_url:
                continue

            resource = build_discovered_resource(
                url=normalized_url,
                source_type="json",
                source_url=source_url,
                course_ref=course_ref,
                title=_resolve_title(current_context),
                file_name=current_context.get("fileName"),
                extension=current_context.get("suffix"),
                mime_type=current_context.get("mime_type"),
                chapter_id=current_context.get("chapterId"),
                object_id=current_context.get("objectId"),
                external_resource_id=current_context.get("resourceId"),
                expected_size=current_context.get("size"),
                expected_md5=current_context.get("md5"),
                raw_context={**current_context, "source_field": field_name},
            )
            if resource is not None:
                resources.append(resource)

    for key, value in node.items():
        if isinstance(value, (dict, list)):
            _walk_json_node(
                value,
                resources,
                source_url=source_url,
                course_ref=course_ref,
                inherited_context=current_context if key in JSON_CONTAINER_FIELDS else dict(current_context),
            )
        elif isinstance(value, str):
            parsed_nested = try_parse_json_text(value)
            if parsed_nested is not None:
                _walk_json_node(
                    parsed_nested,
                    resources,
                    source_url=source_url,
                    course_ref=course_ref,
                    inherited_context=current_context,
                )


def _extract_context_from_mapping(node: Mapping[str, object]) -> dict[str, object]:
    context: dict[str, object] = {}

    for field in TITLE_FIELDS:
        value = node.get(field)
        if isinstance(value, str) and value.strip():
            context[field] = value.strip()

    suffix = node.get("suffix")
    if isinstance(suffix, str) and suffix.strip():
        context["suffix"] = suffix.strip().lstrip(".").lower()

    resource_type = node.get("type")
    if isinstance(resource_type, str) and resource_type.strip():
        context["type"] = resource_type.strip().lstrip(".").lower()

    for field in RESOURCE_ID_FIELDS:
        value = node.get(field)
        if value not in (None, ""):
            context["resourceId"] = str(value).strip()
            break

    for field in OBJECT_ID_FIELDS:
        value = node.get(field)
        if value not in (None, ""):
            context["objectId"] = str(value).strip()
            break

    for field in SIZE_FIELDS:
        value = node.get(field)
        if value not in (None, ""):
            context["size"] = value
            break

    for field in MD5_FIELDS:
        value = node.get(field)
        if value not in (None, ""):
            context["md5"] = str(value).strip()
            break

    for field in CHAPTER_ID_FIELDS:
        value = node.get(field)
        if value not in (None, ""):
            context["chapterId"] = str(value).strip()
            break

    mime_type = node.get("mimeType") or node.get("contentType")
    if isinstance(mime_type, str) and mime_type.strip():
        context["mime_type"] = mime_type.strip()

    courseid = node.get("courseid")
    if courseid not in (None, ""):
        context["courseid"] = str(courseid).strip()

    clazzid = node.get("clazzid")
    if clazzid not in (None, ""):
        context["clazzid"] = str(clazzid).strip()

    return context


def _resolve_title(context: dict[str, object]) -> str | None:
    for field in TITLE_FIELDS:
        value = context.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
