from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser

from .js_resource_discoverer import discover_resources_from_js_text
from .json_resource_discoverer import discover_resources_from_json_text, try_parse_json_text
from .models import ChaoxingCourseRef
from .resource_models import DiscoveredResource, build_discovered_resource, dedupe_discovered_resources
from .url_utils import normalize_and_validate_resource_url

TARGET_TAG_URL_ATTRS = {
    "img": ("src", "data-src", "data-original", "data-url", "data-download-url"),
    "a": ("href", "data-url", "data-download-url"),
    "iframe": ("src", "data-src", "data-url"),
    "embed": ("src", "data-src", "data-url"),
    "object": ("data", "data-src", "data-url"),
    "source": ("src", "data-src", "data-url"),
    "video": ("poster", "src", "data-src", "data-original"),
}
GENERIC_DATA_URL_ATTRS = ("data-url", "data-src", "data-original", "data-download-url")


def discover_resources_from_html(
    html: str,
    page_url: str | None = None,
    course_ref: ChaoxingCourseRef | None = None,
) -> list[DiscoveredResource]:
    parser = _CourseResourceHTMLParser()
    parser.feed(html)
    parser.close()

    resources: list[DiscoveredResource] = []

    for tag_record in parser.tag_records:
        resources.extend(_resources_from_tag_record(tag_record, page_url=page_url, course_ref=course_ref))

    for script_block in parser.script_blocks:
        script_text = script_block.content.strip()
        if not script_text:
            continue

        parsed_json = try_parse_json_text(script_text)
        if parsed_json is not None:
            resources.extend(discover_resources_from_json_text(script_text, source_url=page_url, course_ref=course_ref))
        else:
            resources.extend(discover_resources_from_js_text(script_text, source_url=page_url, course_ref=course_ref))

    for json_text in parser.inline_json_candidates:
        resources.extend(discover_resources_from_json_text(json_text, source_url=page_url, course_ref=course_ref))

    return dedupe_discovered_resources(resources)


def _resources_from_tag_record(
    tag_record: "_TagRecord",
    *,
    page_url: str | None,
    course_ref: ChaoxingCourseRef | None,
) -> list[DiscoveredResource]:
    attrs = tag_record.attrs
    candidate_attr_names = list(TARGET_TAG_URL_ATTRS.get(tag_record.tag, ()))
    for attr_name in GENERIC_DATA_URL_ATTRS:
        if attr_name not in candidate_attr_names:
            candidate_attr_names.append(attr_name)

    resources: list[DiscoveredResource] = []
    seen_urls: set[str] = set()
    for attr_name in candidate_attr_names:
        candidate_url = attrs.get(attr_name)
        normalized_url = normalize_and_validate_resource_url(candidate_url, base_url=page_url) if candidate_url else None
        if not normalized_url or normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)

        resource = build_discovered_resource(
            url=normalized_url,
            source_type="html",
            source_url=page_url,
            course_ref=course_ref,
            title=_resolve_title(tag_record),
            chapter_id=attrs.get("data-chapter-id"),
            object_id=attrs.get("data-objectid") or attrs.get("objectid") or attrs.get("data-fileid"),
            external_resource_id=attrs.get("data-resource-id") or attrs.get("data-fileid"),
            raw_context={
                "tag": tag_record.tag,
                "attr_name": attr_name,
                "class": attrs.get("class"),
                "id": attrs.get("id"),
                "width": attrs.get("width"),
                "height": attrs.get("height"),
                "objectid": attrs.get("data-objectid") or attrs.get("objectid"),
                "fileId": attrs.get("data-fileid"),
            },
        )
        if resource is not None:
            resources.append(resource)

    return resources


def _resolve_title(tag_record: "_TagRecord") -> str | None:
    attrs = tag_record.attrs
    for field in ("title", "alt", "data-title", "data-name"):
        value = attrs.get(field)
        if value and value.strip():
            return value.strip()

    text = tag_record.text.strip()
    return text or None


@dataclass(slots=True)
class _TagRecord:
    tag: str
    attrs: dict[str, str]
    text: str = ""


@dataclass(slots=True)
class _ScriptBlock:
    attrs: dict[str, str]
    content: str


class _CourseResourceHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tag_records: list[_TagRecord] = []
        self.script_blocks: list[_ScriptBlock] = []
        self.inline_json_candidates: list[str] = []
        self._current_anchor: _TagRecord | None = None
        self._current_script_attrs: dict[str, str] | None = None
        self._current_script_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name: value or "" for name, value in attrs if name}

        for attr_value in attr_map.values():
            if attr_value and attr_value.strip().startswith(("{", "[")):
                self.inline_json_candidates.append(attr_value)

        if tag == "script":
            self._current_script_attrs = attr_map
            self._current_script_chunks = []
            return

        if tag == "a":
            self._current_anchor = _TagRecord(tag="a", attrs=attr_map, text="")
            return

        if tag in TARGET_TAG_URL_ATTRS:
            self.tag_records.append(_TagRecord(tag=tag, attrs=attr_map))

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_anchor is not None:
            self.tag_records.append(self._current_anchor)
            self._current_anchor = None
            return

        if tag == "script" and self._current_script_attrs is not None:
            self.script_blocks.append(
                _ScriptBlock(
                    attrs=self._current_script_attrs,
                    content="".join(self._current_script_chunks),
                )
            )
            self._current_script_attrs = None
            self._current_script_chunks = []

    def handle_data(self, data: str) -> None:
        if self._current_anchor is not None:
            self._current_anchor.text += data
        if self._current_script_attrs is not None:
            self._current_script_chunks.append(data)
