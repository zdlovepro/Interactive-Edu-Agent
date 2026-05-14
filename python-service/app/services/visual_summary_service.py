from __future__ import annotations

import shutil
import subprocess
import tempfile
import re
from pathlib import Path

from app.core.config import settings
from app.schemas.parse import PageContent, ParseResult
from app.schemas.visual import VisualSummary
from app.utils.logger import logger

try:  # pragma: no cover - optional dependency
    import fitz  # PyMuPDF
except Exception:  # noqa: BLE001
    fitz = None


def generate_visual_summaries(
    parse_result: ParseResult,
    source_path: str | Path,
    output_dir: str | Path | None = None,
    dpi: int = 144,
) -> tuple[list[VisualSummary], dict[int, str]]:
    """Generate (mock) visual summaries and optionally render page images.

    Returns:
        (summaries, page_images)
        - summaries: list of VisualSummary
        - page_images: mapping from page_index to rendered PNG absolute path
    """

    resolved_source = Path(source_path)
    images: dict[int, str] = {}

    if output_dir is not None:
        resolved_output = Path(output_dir)
    else:
        resolved_output = None

    if parse_result.file_type == "pdf" and resolved_output is not None:
        images = _render_pdf_pages_to_png(resolved_source, resolved_output, dpi=dpi)
    elif parse_result.file_type == "pptx" and resolved_output is not None:
        images = _render_pptx_slides_to_png(resolved_source, resolved_output, dpi=dpi)
    elif resolved_output is not None:
        logger.info(
            "Skip page rendering for non-PDF courseware. coursewareId=%s fileType=%s",
            parse_result.courseware_id,
            parse_result.file_type,
        )

    summaries: list[VisualSummary] = []
    for page in parse_result.pages:
        image_path = images.get(page.page_index)
        summaries.append(build_visual_summary(page, image_path=image_path))
    return summaries, images


def build_visual_summary(page: PageContent, image_path: str | None = None) -> VisualSummary:
    """Build a visual summary for one page.

    Strategy:
    - If VISION config is present and image_path exists: call vision model
    - Otherwise: fallback to deterministic mock summary
    """

    if _vision_enabled() and image_path:
        try:
            from app.clients.vision_client import get_vision_client

            hint_text = "\n".join([item for item in (page.text, page.notes) if item and item.strip()])
            return get_vision_client().summarize_page(
                page_index=page.page_index,
                image_path=image_path,
                hint_text=hint_text if hint_text.strip() else None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Vision summary degraded to mock. pageIndex=%s reason=%s",
                page.page_index,
                str(exc),
            )

    return build_mock_visual_summary(page)


def build_mock_visual_summary(page: PageContent) -> VisualSummary:
    objects = _detect_visual_objects(page)
    summary = _build_mock_summary_text(page, objects)

    return VisualSummary(
        page_index=page.page_index,
        visual_summary=summary,
        objects=objects,
    )


def _detect_visual_objects(page: PageContent) -> list[str]:
    objects: list[str] = []

    if page.formula_placeholders:
        objects.append("公式")

    # Heuristic: tables in PPTX parsing are flattened into text like "a | b | c".
    if _contains_table_like_text(page.text):
        objects.append("表格")

    if page.image_placeholders:
        # Without a vision model, we cannot distinguish photo vs chart reliably.
        objects.append("图表/图片")

        if any("[图表:" in placeholder for placeholder in page.image_placeholders):
            objects.append("图表")
        if any("[流程图:" in placeholder for placeholder in page.image_placeholders):
            objects.append("流程图")
        if any("[示意图:" in placeholder for placeholder in page.image_placeholders):
            objects.append("示意图")

        # Vector drawings in PDF often indicate flowcharts/diagrams.
        if any("矢量图形" in placeholder for placeholder in page.image_placeholders):
            objects.append("流程图/示意图")

    # Deduplicate while keeping order.
    seen: set[str] = set()
    result: list[str] = []
    for item in objects:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _build_mock_summary_text(page: PageContent, objects: list[str]) -> str:
    counts: list[str] = []
    if page.image_placeholders:
        counts.append(f"{len(page.image_placeholders)} 张图片")
    if page.formula_placeholders:
        counts.append(f"{len(page.formula_placeholders)} 个公式")

    if not objects:
        return "本页主要为文本内容，未检测到图表、表格或流程图等显著视觉元素。"

    suffix = "，".join(counts) if counts else "若干视觉元素"
    return f"本页包含 {suffix}。可重点关注：{ '、'.join(objects) }。"


def _contains_table_like_text(text: str | None) -> bool:
    if not text:
        return False
    for line in text.splitlines():
        if line.count("|") >= 2:
            return True
    return False


def _render_pdf_pages_to_png(pdf_path: Path, output_dir: Path, dpi: int = 144) -> dict[int, str]:
    if fitz is None:
        logger.warning("PyMuPDF not installed; skip PDF page rendering. path=%s", pdf_path)
        return {}

    if dpi <= 36:
        dpi = 36

    output_dir.mkdir(parents=True, exist_ok=True)
    images: dict[int, str] = {}

    doc = fitz.open(str(pdf_path))
    try:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        for index in range(doc.page_count):
            page = doc.load_page(index)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            out_path = output_dir / f"page_{index + 1}.png"
            pix.save(str(out_path))
            images[index + 1] = str(out_path)

        logger.info(
            "Rendered PDF pages to PNG. path=%s outDir=%s pageCount=%s",
            pdf_path,
            output_dir,
            doc.page_count,
        )
        return images
    finally:
        doc.close()


def _render_pptx_slides_to_png(pptx_path: Path, output_dir: Path, dpi: int = 144) -> dict[int, str]:
    """Best-effort render PPTX slides to PNG.

    Priority:
    1) LibreOffice (soffice) to PDF, then PyMuPDF render
    2) Windows PowerPoint COM automation (optional dependency)
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1) Try LibreOffice CLI.
    soffice = _find_soffice_executable()
    if soffice:
        try:
            with tempfile.TemporaryDirectory(prefix="pptx_to_pdf_") as tmp_dir:
                tmp_path = Path(tmp_dir)
                _convert_pptx_to_pdf_with_soffice(soffice, pptx_path, tmp_path)

                pdf_candidate = tmp_path / (pptx_path.stem + ".pdf")
                if pdf_candidate.exists():
                    return _render_pdf_pages_to_png(pdf_candidate, output_dir, dpi=dpi)

                # Fallback: pick any produced PDF.
                pdfs = list(tmp_path.glob("*.pdf"))
                if pdfs:
                    return _render_pdf_pages_to_png(pdfs[0], output_dir, dpi=dpi)

                logger.warning("LibreOffice conversion produced no PDF. path=%s", pptx_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LibreOffice PPTX render failed. path=%s reason=%s", pptx_path, str(exc))
    else:
        logger.info("LibreOffice not found (soffice). path=%s", pptx_path)

    # 2) Try PowerPoint COM automation on Windows.
    try:
        return _render_pptx_slides_to_png_with_powerpoint(pptx_path, output_dir)
    except Exception as exc:  # noqa: BLE001
        logger.warning("PowerPoint PPTX render failed. path=%s reason=%s", pptx_path, str(exc))

    logger.info("Skip PPTX slide rendering: no renderer available. path=%s", pptx_path)
    return {}


def _find_soffice_executable() -> str | None:
    """Locate LibreOffice 'soffice' executable.

    We first try PATH, then common Windows install locations.
    """

    candidate = shutil.which("soffice") or shutil.which("soffice.exe")
    if candidate:
        return candidate

    # Common Windows installs.
    common_paths = [
        Path("C:/Program Files/LibreOffice/program/soffice.exe"),
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
    ]
    for path in common_paths:
        try:
            if path.exists() and path.is_file():
                return str(path)
        except Exception:  # noqa: BLE001
            continue
    return None


def _convert_pptx_to_pdf_with_soffice(soffice: str, pptx_path: Path, out_dir: Path) -> None:
    # LibreOffice sometimes needs user profile dir to avoid locking issues.
    user_profile_dir = out_dir / "lo_profile"
    user_profile_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        soffice,
        "--headless",
        f"-env:UserInstallation=file:///{user_profile_dir.as_posix()}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(pptx_path),
    ]

    completed = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"soffice conversion failed (code={completed.returncode}). stderr={completed.stderr[-500:]}"
        )


def _render_pptx_slides_to_png_with_powerpoint(pptx_path: Path, output_dir: Path) -> dict[int, str]:
    """Optional Windows-only path using PowerPoint COM. Requires pywin32."""

    # pragma: no cover - optional dependency + Windows-only
    try:
        import win32com.client  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("pywin32 not installed") from exc

    with tempfile.TemporaryDirectory(prefix="pptx_to_png_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        app = win32com.client.Dispatch("PowerPoint.Application")
        app.Visible = 1
        presentation = None
        try:
            presentation = app.Presentations.Open(str(pptx_path), WithWindow=False)
            # 18 == ppSaveAsPNG
            presentation.SaveAs(str(tmp_path), 18)
        finally:
            try:
                if presentation is not None:
                    presentation.Close()
            finally:
                app.Quit()

        images: dict[int, str] = {}
        for file in tmp_path.glob("*.png"):
            index = _parse_ppt_export_index(file.name)
            if index is None:
                continue
            target = output_dir / f"page_{index}.png"
            shutil.copyfile(file, target)
            images[index] = str(target)
        return images


def _parse_ppt_export_index(filename: str) -> int | None:
    # Common patterns: Slide1.png, 幻灯片1.png
    match = re.search(r"(\d+)", filename)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _vision_enabled() -> bool:
    return bool(settings.VISION_API_KEY and settings.VISION_API_BASE and settings.VISION_MODEL_NAME)
