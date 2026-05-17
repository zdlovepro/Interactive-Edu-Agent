from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from .downloader import DownloadResult
from .errors import NoSlideImagesError

SUPPORTED_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def build_pdf_from_slide_images(
    image_paths: list[Path],
    output_pdf: Path,
    title: str | None = None,
) -> Path:
    slide_paths = [path for path in image_paths if path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES]
    if not slide_paths:
        raise NoSlideImagesError("No slide images available to build a PDF.")

    ordered_paths = sorted(slide_paths, key=_natural_sort_key)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    converted_images: list[Image.Image] = []
    try:
        for path in ordered_paths:
            with Image.open(path) as image:
                converted = image.convert("RGB")
                converted_images.append(converted.copy())

        first, rest = converted_images[0], converted_images[1:]
        save_kwargs = {"save_all": True, "append_images": rest}
        if title:
            save_kwargs["title"] = title
        first.save(output_pdf, format="PDF", **save_kwargs)
    finally:
        for image in converted_images:
            image.close()

    if not output_pdf.exists() or output_pdf.stat().st_size <= 0:
        raise RuntimeError(f"Failed to build PDF at {output_pdf}")

    return output_pdf


def select_slide_images_from_results(results: list[DownloadResult]) -> list[Path]:
    selected_paths: list[Path] = []
    for result in results:
        if result.resource_kind != "slide_image" or result.status != "success" or not result.local_path:
            continue
        candidate = Path(result.local_path)
        if candidate.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES and candidate.exists():
            selected_paths.append(candidate)
    return sorted(selected_paths, key=_natural_sort_key)


def _natural_sort_key(path: Path) -> list[object]:
    name = path.name.lower()
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]
