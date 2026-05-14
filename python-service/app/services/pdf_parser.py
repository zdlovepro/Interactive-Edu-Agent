from __future__ import annotations

from pathlib import Path

import pdfplumber

try:  # pragma: no cover - optional dependency
    import fitz  # PyMuPDF
except Exception:  # noqa: BLE001
    fitz = None

from app.schemas.parse import PageContent, ParseResult
from app.utils.logger import logger


def parse_pdf(file_path: str, courseware_id: str) -> ParseResult:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{file_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"不支持的文件格式：{path.suffix}，期望 .pdf")

    logger.info("Start parsing PDF. coursewareId=%s path=%s", courseware_id, file_path)
    pages: list[PageContent] = []

    fitz_doc = None
    if fitz is not None:
        try:
            fitz_doc = fitz.open(str(path))
        except Exception:  # noqa: BLE001
            fitz_doc = None

    try:
        with pdfplumber.open(str(path)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text() or "").strip()
                image_placeholders = [
                    f"[图片:page_{index}_img_{image_index}]"
                    for image_index, _image in enumerate(page.images, start=1)
                ]

                if fitz_doc is not None and index - 1 < fitz_doc.page_count:
                    try:
                        fitz_page = fitz_doc.load_page(index - 1)
                        # Some PDFs contain vector charts/flow diagrams rather than embedded raster images.
                        fitz_images = fitz_page.get_images(full=True)
                        if len(fitz_images) > len(image_placeholders):
                            for extra_index in range(len(image_placeholders) + 1, len(fitz_images) + 1):
                                image_placeholders.append(f"[图片:page_{index}_img_{extra_index}]")

                        drawings = fitz_page.get_drawings()
                        drawings_count = len(drawings) if drawings else 0
                        # Heuristic: treat pages with noticeable vector drawings as having visual elements.
                        if drawings_count >= 50 or (drawings_count >= 10 and len(text) < 80):
                            image_placeholders.append(f"[矢量图形:page_{index}_drawings_{drawings_count}]")
                    except Exception:  # noqa: BLE001
                        pass

                pages.append(
                    PageContent(
                        page_index=index,
                        text=text,
                        notes="",
                        image_placeholders=image_placeholders,
                        formula_placeholders=[],
                    )
                )
    finally:
        try:
            if fitz_doc is not None:
                fitz_doc.close()
        except Exception:  # noqa: BLE001
            pass

    result = ParseResult(
        courseware_id=courseware_id,
        file_type="pdf",
        total_pages=len(pages),
        pages=pages,
    )
    logger.info("PDF parsing completed. coursewareId=%s totalPages=%s", courseware_id, result.total_pages)
    return result
