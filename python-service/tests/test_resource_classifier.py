from __future__ import annotations

import struct
import zlib
from pathlib import Path

from app.course_resource_importer.resource_classifier import ImageProbe, classify_resource, classify_resources
from app.course_resource_importer.resource_models import DiscoveredResource


def test_machine_learning_cover_png_large_4_3_is_slide_image(tmp_path: Path):
    image_path = tmp_path / "Machine-Learning-cover.png"
    _write_png(image_path, 1024, 768)
    resource = _resource(
        url="https://mooc1.chaoxing.com/courseware/Machine-Learning-cover.png",
        extension="png",
        file_name="Machine-Learning-cover.png",
        raw_context={"local_path": str(image_path), "tag": "img"},
    )

    classified = classify_resource(resource, image_probe=ImageProbe())

    assert classified.resource_kind == "slide_image"
    assert classified.confidence >= 0.8


def test_large_16_9_image_is_slide_image():
    resource = _resource(
        url="https://mooc1.chaoxing.com/preview/page_1.jpg",
        extension="jpg",
        file_name="page_1.jpg",
        raw_context={"width": 1280, "height": 720, "tag": "img"},
    )

    classified = classify_resource(resource)

    assert classified.resource_kind == "slide_image"
    assert "aspect ratio" in classified.reason


def test_large_4_3_image_is_slide_image():
    resource = _resource(
        url="https://mooc1.chaoxing.com/document/slide001.jpeg",
        extension="jpeg",
        file_name="slide001.jpeg",
        raw_context={"width": 1024, "height": 768, "tag": "img"},
    )

    classified = classify_resource(resource)

    assert classified.resource_kind == "slide_image"


def test_icon_assistant_png_is_ui_asset():
    resource = _resource(
        url="https://mooc1.chaoxing.com/static/icon-assistant.png",
        extension="png",
        file_name="icon-assistant.png",
        raw_context={"width": 32, "height": 32, "tag": "img"},
    )

    classified = classify_resource(resource)

    assert classified.resource_kind == "ui_asset"


def test_read_loading_gif_is_ui_asset():
    resource = _resource(
        url="https://mooc1.chaoxing.com/static/read-loading.gif",
        extension="gif",
        file_name="read-loading.gif",
    )

    classified = classify_resource(resource)

    assert classified.resource_kind == "ui_asset"


def test_baguettebox_js_is_not_courseware():
    resource = _resource(
        url="https://mooc1.chaoxing.com/static/baguettebox.min.js",
        extension="js",
        file_name="baguettebox.min.js",
    )

    classified = classify_resource(resource)

    assert classified.resource_kind in {"ui_asset", "unknown"}
    assert classified.resource_kind != "courseware_file"


def test_pptx_is_courseware_file():
    resource = _resource(
        url="https://mooc1.chaoxing.com/files/lesson.pptx",
        extension="pptx",
        file_name="lesson.pptx",
    )

    classified = classify_resource(resource)

    assert classified.resource_kind == "courseware_file"
    assert classified.confidence >= 0.95


def test_pdf_is_courseware_file():
    resource = _resource(
        url="https://mooc1.chaoxing.com/files/lesson.pdf",
        extension="pdf",
        file_name="lesson.pdf",
    )

    classified = classify_resource(resource)

    assert classified.resource_kind == "courseware_file"


def test_docx_is_attachment():
    resource = _resource(
        url="https://mooc1.chaoxing.com/files/notes.docx",
        extension="docx",
        file_name="notes.docx",
    )

    classified = classify_resource(resource)

    assert classified.resource_kind == "attachment"


def test_small_logo_png_is_ui_asset():
    resource = _resource(
        url="https://mooc1.chaoxing.com/static/logo.png",
        extension="png",
        file_name="logo.png",
        raw_context={"width": 96, "height": 96, "tag": "img"},
    )

    classified = classify_resource(resource)

    assert classified.resource_kind == "ui_asset"


def test_small_uncertain_image_is_unknown_or_ui_asset():
    resource = _resource(
        url="https://mooc1.chaoxing.com/assets/pic.png",
        extension="png",
        file_name="pic.png",
        raw_context={"width": 120, "height": 90, "tag": "img"},
    )

    classified = classify_resource(resource)

    assert classified.resource_kind in {"unknown", "ui_asset"}


def test_sequence_images_get_promoted_to_slide_images():
    resources = [
        _resource(
            url="https://mooc1.chaoxing.com/preview/slide_001.png",
            extension="png",
            file_name="slide_001.png",
            raw_context={"width": 960, "height": 540, "tag": "img"},
        ),
        _resource(
            url="https://mooc1.chaoxing.com/preview/slide_002.png",
            extension="png",
            file_name="slide_002.png",
            raw_context={"width": 960, "height": 540, "tag": "img"},
        ),
    ]

    classified = classify_resources(resources)

    assert all(item.resource_kind == "slide_image" for item in classified)
    assert all("sequential page set" in item.reason for item in classified)


def _resource(
    *,
    url: str,
    extension: str,
    file_name: str,
    raw_context: dict | None = None,
) -> DiscoveredResource:
    return DiscoveredResource(
        resource_id=f"res:{file_name}",
        url=url,
        file_name=file_name,
        extension=extension,
        source_type="html",
        raw_context=dict(raw_context or {}),
    )


def _write_png(path: Path, width: int, height: int) -> None:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = _png_chunk(b"IHDR", ihdr_data)
    idat = _png_chunk(b"IDAT", zlib.compress(b"\x00" * (height * (1 + width * 3))))
    iend = _png_chunk(b"IEND", b"")
    path.write_bytes(signature + ihdr + idat + iend)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc
