from __future__ import annotations

import json
from pathlib import Path

import pdfplumber
import pytest
from PIL import Image

from app.course_resource_importer.cli import main as importer_cli_main
from app.course_resource_importer.downloader import DownloadResult
from app.course_resource_importer.errors import NoSlideImagesError
from app.course_resource_importer.pdf_builder import build_pdf_from_slide_images, select_slide_images_from_results


def test_build_pdf_from_three_images_creates_three_pages(tmp_path: Path):
    image_paths = [
        _write_rgb_image(tmp_path / "slide_001.png", (1024, 768), "red"),
        _write_rgb_image(tmp_path / "slide_002.png", (1280, 720), "green"),
        _write_rgb_image(tmp_path / "slide_003.jpg", (960, 540), "blue"),
    ]
    output_pdf = tmp_path / "courseware_from_images.pdf"

    built_pdf = build_pdf_from_slide_images(image_paths, output_pdf, title="Machine Learning")

    assert built_pdf.exists()
    assert built_pdf.stat().st_size > 0
    with pdfplumber.open(built_pdf) as pdf:
        assert len(pdf.pages) == 3


def test_build_pdf_from_empty_list_raises():
    with pytest.raises(NoSlideImagesError):
        build_pdf_from_slide_images([], Path("unused.pdf"))


def test_slide_images_are_naturally_sorted(tmp_path: Path):
    images = [
        _write_rgb_image(tmp_path / "10.png", (800, 600), "red"),
        _write_rgb_image(tmp_path / "2.png", (800, 600), "green"),
        _write_rgb_image(tmp_path / "1.png", (800, 600), "blue"),
    ]
    output_pdf = tmp_path / "sorted.pdf"

    build_pdf_from_slide_images(images, output_pdf)

    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 0


def test_rgba_png_can_be_converted_to_pdf(tmp_path: Path):
    rgba_path = tmp_path / "slide_001.png"
    Image.new("RGBA", (1024, 768), (255, 0, 0, 180)).save(rgba_path)
    output_pdf = tmp_path / "rgba.pdf"

    build_pdf_from_slide_images([rgba_path], output_pdf)

    with pdfplumber.open(output_pdf) as pdf:
        assert len(pdf.pages) == 1


def test_select_slide_images_from_results_filters_successful_slide_images(tmp_path: Path):
    slide_path = _write_rgb_image(tmp_path / "slide_001.png", (1024, 768), "red")
    attachment_path = _write_rgb_image(tmp_path / "attachment.png", (800, 600), "green")
    results = [
        DownloadResult(
            resource_id="slide",
            url="https://example.com/slide_001.png",
            status="success",
            local_path=str(slide_path),
            file_name="slide_001.png",
            resource_kind="slide_image",
            size_bytes=slide_path.stat().st_size,
            md5=None,
            sha256=None,
            error_message=None,
        ),
        DownloadResult(
            resource_id="attachment",
            url="https://example.com/attachment.png",
            status="success",
            local_path=str(attachment_path),
            file_name="attachment.png",
            resource_kind="content_image",
            size_bytes=attachment_path.stat().st_size,
            md5=None,
            sha256=None,
            error_message=None,
        ),
        DownloadResult(
            resource_id="failed-slide",
            url="https://example.com/slide_002.png",
            status="failed",
            local_path=str(tmp_path / "slide_002.png"),
            file_name="slide_002.png",
            resource_kind="slide_image",
            size_bytes=None,
            md5=None,
            sha256=None,
            error_message="failed",
        ),
    ]

    selected = select_slide_images_from_results(results)

    assert selected == [slide_path]


def test_cli_build_pdf_from_manifest(tmp_path: Path):
    slide_path = _write_rgb_image(tmp_path / "slide_001.png", (1024, 768), "red")
    manifest_path = tmp_path / "manifest.json"
    output_pdf = tmp_path / "courseware_from_images.pdf"
    manifest_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "resource_id": "slide",
                        "url": "https://example.com/slide_001.png",
                        "status": "success",
                        "local_path": str(slide_path),
                        "file_name": "slide_001.png",
                        "resource_kind": "slide_image",
                        "size_bytes": slide_path.stat().st_size,
                        "md5": None,
                        "sha256": None,
                        "error_message": None,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    exit_code = importer_cli_main(["build-pdf", "--manifest", str(manifest_path), "--output", str(output_pdf)])

    assert exit_code == 0
    assert output_pdf.exists()
    with pdfplumber.open(output_pdf) as pdf:
        assert len(pdf.pages) == 1


def test_cli_supports_build_pdf_flag(tmp_path: Path):
    slide_path = _write_rgb_image(tmp_path / "slide_002.png", (1280, 720), "green")
    manifest_path = tmp_path / "manifest.json"
    output_pdf = tmp_path / "courseware_from_images.pdf"
    manifest_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "resource_id": "slide-2",
                        "url": "https://example.com/slide_002.png",
                        "status": "success",
                        "local_path": str(slide_path),
                        "file_name": "slide_002.png",
                        "resource_kind": "slide_image",
                        "size_bytes": slide_path.stat().st_size,
                        "md5": None,
                        "sha256": None,
                        "error_message": None,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    exit_code = importer_cli_main(
        ["--build-pdf", "true", "--manifest", str(manifest_path), "--output", str(output_pdf)]
    )

    assert exit_code == 0
    assert output_pdf.exists()


def test_generated_pdf_can_be_read_by_pdfplumber(tmp_path: Path):
    image_paths = [
        _write_rgb_image(tmp_path / "page-1.jpg", (1200, 675), "red"),
        _write_rgb_image(tmp_path / "page-2.jpg", (1200, 675), "green"),
    ]
    output_pdf = tmp_path / "parse_ready.pdf"

    build_pdf_from_slide_images(image_paths, output_pdf)

    with pdfplumber.open(output_pdf) as pdf:
        assert len(pdf.pages) == 2
        assert pdf.pages[0].width > 0
        assert pdf.pages[0].height > 0


def _write_rgb_image(path: Path, size: tuple[int, int], color: str) -> Path:
    Image.new("RGB", size, color).save(path)
    return path
