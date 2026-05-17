from __future__ import annotations

import json
import re

from .json_resource_discoverer import discover_resources_from_json, try_parse_json_text
from .models import ChaoxingCourseRef
from .resource_models import DiscoveredResource, build_discovered_resource, dedupe_discovered_resources
from .url_utils import normalize_and_validate_resource_url

URL_LITERAL_PATTERN = re.compile(r"""(?P<quote>["'])(?P<url>(?:https?://|/)[^"'<>\\\s]+)(?P=quote)""")
FIELD_URL_PATTERN = re.compile(
    r"""(?P<field>fileinfo\s*\.\s*download|downloadUrl|download|objectUrl|fileUrl|pptUrl|pdfUrl|previewUrl|resourceUrl)\s*[:=]\s*(?P<quote>["'])(?P<url>[^"'<>\\\s]+)(?P=quote)""",
    re.IGNORECASE,
)
INTERESTING_FIELD_HINTS = ("download", "downloadUrl", "fileUrl", "pptUrl", "pdfUrl", "previewUrl", "resourceUrl")


def discover_resources_from_js_text(
    js_text: str,
    source_url: str | None = None,
    course_ref: ChaoxingCourseRef | None = None,
) -> list[DiscoveredResource]:
    resources: list[DiscoveredResource] = []

    for match in FIELD_URL_PATTERN.finditer(js_text):
        normalized_url = normalize_and_validate_resource_url(match.group("url"), base_url=source_url)
        if not normalized_url:
            continue

        field_name = re.sub(r"\s+", "", match.group("field"))
        resource = build_discovered_resource(
            url=normalized_url,
            source_type="js",
            source_url=source_url,
            course_ref=course_ref,
            raw_context={"source_field": field_name},
        )
        if resource is not None:
            resources.append(resource)

    for parsed in _extract_json_like_objects(js_text):
        resources.extend(discover_resources_from_json(parsed, source_url=source_url, course_ref=course_ref))

    for match in URL_LITERAL_PATTERN.finditer(js_text):
        normalized_url = normalize_and_validate_resource_url(match.group("url"), base_url=source_url)
        if not normalized_url:
            continue

        resource = build_discovered_resource(
            url=normalized_url,
            source_type="js",
            source_url=source_url,
            course_ref=course_ref,
            raw_context={"source_field": "url_literal"},
        )
        if resource is not None:
            resources.append(resource)

    return dedupe_discovered_resources(resources)


def _extract_json_like_objects(js_text: str) -> list[dict | list]:
    parsed_objects: list[dict | list] = []

    direct_json = try_parse_json_text(js_text)
    if direct_json is not None:
        parsed_objects.append(direct_json)

    for block in _extract_braced_blocks(js_text):
        if not any(hint in block for hint in INTERESTING_FIELD_HINTS):
            continue

        parsed = _try_parse_js_object(block)
        if parsed is not None:
            parsed_objects.append(parsed)

    return parsed_objects


def _extract_braced_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    start_index: int | None = None
    depth = 0
    in_string: str | None = None
    escape_next = False

    for index, char in enumerate(text):
        if in_string:
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
            elif char == in_string:
                in_string = None
            continue

        if char in {"'", '"'}:
            in_string = char
            continue

        if char == "{":
            if depth == 0:
                start_index = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start_index is not None:
                blocks.append(text[start_index : index + 1])
                start_index = None

    return blocks


def _try_parse_js_object(block: str) -> dict | list | None:
    candidate = block.strip().rstrip(";")
    candidate = re.sub(r"/\*.*?\*/", "", candidate, flags=re.DOTALL)
    candidate = re.sub(r"//.*?$", "", candidate, flags=re.MULTILINE)
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    candidate = re.sub(
        r'([{,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)(\s*:)',
        lambda match: f'{match.group(1)}"{match.group(2)}"{match.group(3)}',
        candidate,
    )
    candidate = re.sub(r"\bundefined\b", "null", candidate)
    candidate = candidate.replace("'", '"')

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, (dict, list)) else None
