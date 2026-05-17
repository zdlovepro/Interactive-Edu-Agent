from __future__ import annotations

import struct
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Protocol
from urllib.parse import unquote, urlsplit

from .resource_models import (
    ATTACHMENT_EXTENSIONS,
    COURSEWARE_EXTENSIONS,
    IMAGE_EXTENSIONS,
    DiscoveredResource,
)

UI_KEYWORDS = (
    "icon",
    "logo",
    "avatar",
    "button",
    "btn",
    "toolbar",
    "bg",
    "background",
    "loading",
    "sprite",
    "arrow",
    "select",
    "close",
    "refresh",
    "copy",
    "assistant",
    "translation",
    "translate",
    "read",
    "voice",
    "ai",
    "baguettebox",
    "aplus",
    "queue",
)
SLIDE_PATH_KEYWORDS = (
    "slide",
    "ppt",
    "page",
    "preview",
    "view",
    "document",
    "attachment",
    "object",
    "courseware",
    "ans-attach",
    "mooc",
    "cover",
)
SLIDE_CONTEXT_KEYWORDS = (
    "课件",
    "ppt",
    "pdf",
    "文档",
    "附件",
    "学习资料",
    "chapter",
    "course",
)
SLIDE_ASPECT_RATIOS = (4 / 3, 16 / 9, 16 / 10)
SLIDE_ASPECT_TOLERANCE = 0.18


class ImageProbeLike(Protocol):
    def get_dimensions(self, resource: DiscoveredResource) -> tuple[int, int] | None: ...


@dataclass(slots=True)
class ImageProbe:
    def get_dimensions(self, resource: DiscoveredResource) -> tuple[int, int] | None:
        width = _coerce_positive_int(resource.raw_context.get("width"))
        height = _coerce_positive_int(resource.raw_context.get("height"))
        if width and height:
            return width, height

        for key in ("local_path", "download_path", "path"):
            local_path = resource.raw_context.get(key)
            if not local_path:
                continue

            probed = _probe_image_dimensions_from_path(Path(str(local_path)))
            if probed is not None:
                return probed

        return None


def classify_resource(
    resource: DiscoveredResource,
    image_probe: ImageProbeLike | None = None,
) -> DiscoveredResource:
    return _classify_resource(resource, image_probe=image_probe, sequence_candidate=False)


def classify_resources(
    resources: list[DiscoveredResource],
    image_probe: ImageProbeLike | None = None,
) -> list[DiscoveredResource]:
    sequence_candidates = _find_sequence_candidate_ids(resources)
    return [
        _classify_resource(
            resource,
            image_probe=image_probe,
            sequence_candidate=resource.resource_id in sequence_candidates,
        )
        for resource in resources
    ]


def _classify_resource(
    resource: DiscoveredResource,
    *,
    image_probe: ImageProbeLike | None,
    sequence_candidate: bool,
) -> DiscoveredResource:
    extension = resource.extension.lower().lstrip(".")
    dimensions = image_probe.get_dimensions(resource) if image_probe else _dimensions_from_context(resource)
    width, height = dimensions or (None, None)
    haystack = _build_haystack(resource)

    if extension in COURSEWARE_EXTENSIONS:
        return _replace_resource(resource, "courseware_file", 0.97, f"extension .{extension} recognized as courseware file")

    if extension in ATTACHMENT_EXTENSIONS:
        return _replace_resource(resource, "attachment", 0.92, f"extension .{extension} recognized as attachment")

    if extension in {"json"} or _looks_like_metadata(resource, extension):
        return _replace_resource(resource, "metadata", 0.72, "JSON/JS-style resource likely contains metadata, not downloadable courseware")

    if extension in {"js", "css"}:
        if any(keyword in haystack for keyword in UI_KEYWORDS):
            return _replace_resource(resource, "ui_asset", 0.96, "plugin/static asset path ignored")
        return _replace_resource(resource, "unknown", 0.18, "script or stylesheet is not a courseware file")

    if extension == "gif":
        if any(keyword in haystack for keyword in ("loading", "read", "voice", "assistant")):
            return _replace_resource(resource, "ui_asset", 0.97, "filename contains loading/read/voice, ignored as ui asset")
        return _replace_resource(resource, "unknown", 0.22, "GIF is not treated as a primary courseware resource")

    if extension not in IMAGE_EXTENSIONS:
        return _replace_resource(resource, "unknown", 0.2, f"extension .{extension or 'unknown'} cannot be confidently classified")

    if _is_ui_asset(haystack, width, height, resource):
        if width is not None and height is not None and width <= 128 and height <= 128:
            reason = "small icon-like image, ignored"
        elif any(keyword in haystack for keyword in UI_KEYWORDS):
            reason = "filename/path matched UI asset keywords"
        else:
            reason = "image matched UI asset heuristics"
        return _replace_resource(resource, "ui_asset", 0.95, reason)

    slide_reasons: list[str] = []
    slide_score = 0.0
    if width is not None and height is not None and width >= 600 and height >= 400:
        slide_score += 1.0
        slide_reasons.append(f"large image {width}x{height}")
    if width is not None and height is not None and _is_slide_aspect_ratio(width, height):
        slide_score += 1.0
        slide_reasons.append("aspect ratio close to slide page")
    if any(keyword in haystack for keyword in SLIDE_PATH_KEYWORDS):
        slide_score += 0.85
        slide_reasons.append("filename/path contains slide-like keywords")
    if _has_context_keywords(resource):
        slide_score += 0.7
        slide_reasons.append("context suggests courseware or attachment")
    if sequence_candidate:
        slide_score += 0.65
        slide_reasons.append("image belongs to a sequential page set")

    if slide_score >= 2.0:
        confidence = min(0.99, 0.55 + slide_score * 0.14)
        return _replace_resource(resource, "slide_image", confidence, "; ".join(slide_reasons) or "large slide-like image")

    if width is not None and height is not None and width >= 300 and height >= 200 and _referenced_by_content(resource):
        return _replace_resource(resource, "content_image", 0.78, "image referenced by course content and large enough")

    if width is not None and height is not None and width <= 160 and height <= 160:
        return _replace_resource(resource, "ui_asset", 0.84, "small image likely belongs to the page UI")

    if width is not None and height is not None and width >= 300 and height >= 200:
        return _replace_resource(resource, "content_image", 0.64, "large image but lacks strong slide-page cues")

    return _replace_resource(resource, "unknown", 0.3, "image lacks enough signals to classify confidently")


def _replace_resource(
    resource: DiscoveredResource,
    resource_kind: str,
    confidence: float,
    reason: str,
) -> DiscoveredResource:
    updated_context = dict(resource.raw_context)
    return replace(
        resource,
        resource_kind=resource_kind,
        confidence=confidence,
        reason=reason,
        raw_context=updated_context,
    )


def _looks_like_metadata(resource: DiscoveredResource, extension: str) -> bool:
    mime = (resource.mime_type or "").lower()
    source_field = str(resource.raw_context.get("source_field") or "").lower()
    if "json" in mime or "javascript" in mime:
        return True
    if resource.source_type in {"json", "js", "api"} and extension == "":
        return source_field in {"url_literal", ""} or "json" in source_field or "fileinfo" in source_field
    return False


def _build_haystack(resource: DiscoveredResource) -> str:
    parts = [
        resource.url,
        resource.file_name,
        resource.title,
        resource.mime_type,
        resource.source_url,
        resource.raw_context.get("class"),
        resource.raw_context.get("id"),
        resource.raw_context.get("tag"),
        resource.raw_context.get("attr_name"),
        resource.raw_context.get("source_field"),
        resource.raw_context.get("style"),
        resource.raw_context.get("name"),
        resource.raw_context.get("title"),
    ]
    return " ".join(str(part or "").lower() for part in parts)


def _dimensions_from_context(resource: DiscoveredResource) -> tuple[int, int] | None:
    width = _coerce_positive_int(resource.raw_context.get("width"))
    height = _coerce_positive_int(resource.raw_context.get("height"))
    if width and height:
        return width, height
    return None


def _is_ui_asset(haystack: str, width: int | None, height: int | None, resource: DiscoveredResource) -> bool:
    if any(keyword in haystack for keyword in UI_KEYWORDS):
        return True
    if width is not None and height is not None and width <= 128 and height <= 128:
        return True
    if resource.raw_context.get("attr_name") == "style":
        return True
    return False


def _is_slide_aspect_ratio(width: int, height: int) -> bool:
    if width <= 0 or height <= 0:
        return False
    ratio = width / height
    return any(abs(ratio - target) <= SLIDE_ASPECT_TOLERANCE for target in SLIDE_ASPECT_RATIOS)


def _has_context_keywords(resource: DiscoveredResource) -> bool:
    context_text = " ".join(
        str(part or "").lower()
        for part in (
            resource.title,
            resource.raw_context.get("name"),
            resource.raw_context.get("title"),
            resource.raw_context.get("source_field"),
            resource.raw_context.get("tag"),
            resource.raw_context.get("attr_name"),
        )
    )
    return any(keyword in context_text for keyword in SLIDE_CONTEXT_KEYWORDS)


def _referenced_by_content(resource: DiscoveredResource) -> bool:
    return str(resource.raw_context.get("tag") or "").lower() == "img"


def _find_sequence_candidate_ids(resources: list[DiscoveredResource]) -> set[str]:
    groups: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for resource in resources:
        if resource.extension.lower() not in IMAGE_EXTENSIONS:
            continue
        sequence = _extract_sequence_signature(resource)
        if sequence is None:
            continue
        group_key, number = sequence
        groups.setdefault(group_key, []).append((number, resource.resource_id))

    candidate_ids: set[str] = set()
    for items in groups.values():
        if len(items) < 2:
            continue
        ordered = sorted(items)
        numbers = [number for number, _ in ordered]
        consecutive_pairs = sum(1 for index in range(1, len(numbers)) if numbers[index] - numbers[index - 1] == 1)
        if consecutive_pairs >= 1:
            candidate_ids.update(resource_id for _, resource_id in ordered)

    return candidate_ids


def _extract_sequence_signature(resource: DiscoveredResource) -> tuple[tuple[str, str], int] | None:
    file_name = resource.file_name or PurePosixPath(unquote(urlsplit(resource.url).path)).name
    if not file_name:
        return None

    stem = PurePosixPath(file_name).stem.lower()
    extension = resource.extension.lower()
    for separator in ("-", "_", " "):
        if separator in stem:
            prefix, maybe_number = stem.rsplit(separator, 1)
            if maybe_number.isdigit():
                return ((prefix, extension), int(maybe_number))

    if stem.isdigit():
        return (("numeric", extension), int(stem))

    suffix_digits = ""
    for char in reversed(stem):
        if char.isdigit():
            suffix_digits = char + suffix_digits
        else:
            break
    if suffix_digits:
        prefix = stem[: -len(suffix_digits)]
        return ((prefix.rstrip("-_ "), extension), int(suffix_digits))

    return None


def _coerce_positive_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _probe_image_dimensions_from_path(path: Path) -> tuple[int, int] | None:
    if not path.exists() or not path.is_file():
        return None

    with path.open("rb") as file:
        header = file.read(64)
        if len(header) < 10:
            return None

        if header.startswith(b"\x89PNG\r\n\x1a\n") and len(header) >= 24:
            width, height = struct.unpack(">II", header[16:24])
            return width, height

        if header[:6] in {b"GIF87a", b"GIF89a"}:
            width, height = struct.unpack("<HH", header[6:10])
            return width, height

        if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            return _probe_webp_dimensions(file, header)

        if header.startswith(b"\xff\xd8"):
            file.seek(0)
            return _probe_jpeg_dimensions(file)

    return None


def _probe_jpeg_dimensions(file) -> tuple[int, int] | None:
    file.read(2)
    while True:
        marker_prefix = file.read(1)
        if not marker_prefix:
            return None
        if marker_prefix != b"\xff":
            continue

        marker = file.read(1)
        if not marker or marker == b"\xd9":
            return None
        while marker == b"\xff":
            marker = file.read(1)
            if not marker:
                return None

        if marker in {b"\xd8", b"\x01"} or 0xD0 <= marker[0] <= 0xD7:
            continue

        segment_length_bytes = file.read(2)
        if len(segment_length_bytes) != 2:
            return None
        segment_length = struct.unpack(">H", segment_length_bytes)[0]
        if segment_length < 2:
            return None

        if marker in {b"\xc0", b"\xc1", b"\xc2", b"\xc3", b"\xc5", b"\xc6", b"\xc7", b"\xc9", b"\xca", b"\xcb", b"\xcd", b"\xce", b"\xcf"}:
            payload = file.read(5)
            if len(payload) != 5:
                return None
            height, width = struct.unpack(">HH", payload[1:5])
            return width, height

        file.seek(segment_length - 2, 1)


def _probe_webp_dimensions(file, header: bytes) -> tuple[int, int] | None:
    chunk_type = header[12:16]
    if chunk_type == b"VP8X" and len(header) >= 30:
        width = 1 + int.from_bytes(header[24:27], "little")
        height = 1 + int.from_bytes(header[27:30], "little")
        return width, height

    if chunk_type == b"VP8 ":
        file.seek(20)
        frame_header = file.read(10)
        if len(frame_header) >= 10 and frame_header[3:6] == b"\x9d\x01\x2a":
            width = struct.unpack("<H", frame_header[6:8])[0] & 0x3FFF
            height = struct.unpack("<H", frame_header[8:10])[0] & 0x3FFF
            return width, height

    if chunk_type == b"VP8L":
        file.seek(21)
        payload = file.read(4)
        if len(payload) == 4:
            bits = int.from_bytes(payload, "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return width, height

    return None
