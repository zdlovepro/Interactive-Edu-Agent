from __future__ import annotations

from pathlib import Path

from app.core.exceptions import (
    AppException,
    BUSINESS_VALIDATION_FAILED,
    NOT_IMPLEMENTED,
    PARAM_ERROR,
    PythonServiceException,
)
from app.schemas.parse import ParseRequest, ParseResult
from app.utils.logger import logger


def parse_courseware_file(request: ParseRequest) -> dict[str, object]:
    logger.info(
        "Parse request received. coursewareId=%s storage=%s fileName=%s",
        request.courseware_id,
        request.normalized_storage,
        request.file_name or "",
    )

    if request.normalized_storage == "local":
        local_path = _resolve_local_path(request)
        if local_path is None:
            target = request.key or request.preferred_name or "<unknown>"
            raise AppException(BUSINESS_VALIDATION_FAILED, f"local courseware file not found: {target}")

        try:
            result = _parse_local_file(local_path, request)
        except FileNotFoundError as exc:
            raise AppException(BUSINESS_VALIDATION_FAILED, str(exc)) from exc
        except ValueError as exc:
            raise AppException(PARAM_ERROR, str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Local parse failed. coursewareId=%s path=%s", request.courseware_id, local_path)
            raise PythonServiceException("课件解析失败") from exc

        visual_summary_by_page: dict[int, object] = {}
        page_images: dict[int, str] = {}
        visual_pages_dir = _courseware_root() / request.courseware_id / "visual" / "pages"
        try:
            from app.services.visual_summary_service import generate_visual_summaries

            summaries, rendered_images = generate_visual_summaries(
                parse_result=result,
                source_path=local_path,
                output_dir=visual_pages_dir,
            )
            visual_summary_by_page = {item.page_index: item for item in summaries}
            page_images = rendered_images
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Visual summary generation skipped. coursewareId=%s reason=%s",
                request.courseware_id,
                str(exc),
            )

        page_images = _ensure_page_images(result, page_images, visual_pages_dir)
        payload = _build_contract_payload(
            result,
            request.preferred_name,
            visual_summary_by_page=visual_summary_by_page,
            page_images=page_images,
        )

        _best_effort_ingest(request, payload)
        return payload

    if request.normalized_storage == "minio":
        raise AppException(
            NOT_IMPLEMENTED,
            f"minio courseware parsing is not implemented yet, key={request.key or '<empty>'}",
        )

    raise AppException(PARAM_ERROR, f"unsupported storage: {request.storage}")


def _parse_local_file(local_path: Path, request: ParseRequest) -> ParseResult:
    suffix = _detect_suffix(local_path, request)
    if suffix == ".pptx":
        from app.services.ppt_parser import parse_pptx

        return parse_pptx(str(local_path), request.courseware_id)
    if suffix == ".pdf":
        from app.services.pdf_parser import parse_pdf

        return parse_pdf(str(local_path), request.courseware_id)
    raise ValueError(f"unsupported file type: {suffix}")


def _build_contract_payload(
    result: ParseResult,
    preferred_name: str | None,
    visual_summary_by_page: dict[int, object] | None = None,
    page_images: dict[int, str] | None = None,
) -> dict[str, object]:
    outline: list[str] = []
    segments: list[dict[str, object]] = []
    page_details: list[dict[str, object]] = []
    default_topic = Path(preferred_name or result.courseware_id).stem or result.courseware_id

    visual_summary_by_page = visual_summary_by_page or {}
    page_images = page_images or {}

    for page in result.pages:
        title = _derive_title(page, default_topic)
        content = _merge_page_content(page)
        visual_summary_item = visual_summary_by_page.get(page.page_index)
        visual_summary_text, visual_objects = _resolve_visual_summary(page, visual_summary_item)
        page_image_path = page_images.get(page.page_index)
        outline.append(title)
        segment: dict[str, object] = {
            "pageIndex": page.page_index,
            "title": title,
            "content": content,
            "knowledgePoints": _derive_knowledge_points(title, default_topic),
            "visualSummary": visual_summary_text,
            "visualObjects": visual_objects,
        }

        if page_image_path:
            segment["pageImagePath"] = page_image_path

        segments.append(segment)

        page_details.append(
            {
                "pageNo": page.page_index,
                "text": content,
                "imagePath": page_image_path,
                "visualSummary": visual_summary_text,
                "formulas": list(page.formula_placeholders),
                "charts": _derive_charts(page.image_placeholders),
                "diagrams": _derive_diagrams(page.image_placeholders),
            }
        )

    return {
        "coursewareId": result.courseware_id,
        "pages": result.total_pages,
        "outline": outline,
        "segments": segments,
        "pageDetails": page_details,
    }


def _ensure_page_images(result: ParseResult, page_images: dict[int, str], output_dir: Path) -> dict[int, str]:
    resolved = dict(page_images)
    missing_pages = [page.page_index for page in result.pages if page.page_index not in resolved]
    if not missing_pages:
        return resolved

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        for page_index in missing_pages:
            image_path = output_dir / f"page_{page_index}.png"
            if not image_path.exists():
                _write_fallback_page_image(image_path, page_index)
            resolved[page_index] = str(image_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Fallback page image generation skipped. coursewareId=%s reason=%s",
            result.courseware_id,
            str(exc),
        )
    return resolved


def _write_fallback_page_image(path: Path, page_index: int) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1280, 720), color=(246, 248, 250))
    draw = ImageDraw.Draw(image)
    draw.rectangle((64, 64, 1216, 656), outline=(120, 130, 140), width=3)
    draw.text((96, 96), f"Courseware Page {page_index}", fill=(40, 50, 60))
    draw.text((96, 136), "Rendered page image unavailable; using fallback preview.", fill=(80, 90, 100))
    image.save(path)


def _resolve_visual_summary(page, visual_summary_item: object | None) -> tuple[str, list[str]]:
    if visual_summary_item is not None:
        summary = getattr(visual_summary_item, "visual_summary", None)
        objects = getattr(visual_summary_item, "objects", None)
        if isinstance(summary, str) and summary.strip():
            return summary, list(objects) if isinstance(objects, list) else []

    try:
        from app.services.visual_summary_service import build_mock_visual_summary

        fallback = build_mock_visual_summary(page)
        return fallback.visual_summary, fallback.objects
    except Exception:  # noqa: BLE001
        return "本页视觉摘要暂不可用，已保留页面文本用于后续问答。", []


def _derive_charts(image_placeholders: list[str]) -> list[str]:
    return [item for item in image_placeholders if "图表" in item]


def _derive_diagrams(image_placeholders: list[str]) -> list[str]:
    return [item for item in image_placeholders if any(keyword in item for keyword in ("流程图", "示意图", "矢量图形"))]


def _derive_title(page, default_topic: str) -> str:
    first_line = next((line.strip() for line in page.text.splitlines() if line.strip()), "")
    if first_line:
        return first_line[:48]
    if page.notes:
        note_line = next((line.strip() for line in page.notes.splitlines() if line.strip()), "")
        if note_line:
            return note_line[:48]
    return f"{default_topic}-第{page.page_index}页"


def _merge_page_content(page) -> str:
    parts = [part.strip() for part in (page.text, page.notes) if part and part.strip()]
    if parts:
        return "\n".join(parts)
    return f"第{page.page_index}页暂无可提取文本内容。"


def _derive_knowledge_points(title: str, default_topic: str) -> list[str]:
    points = [default_topic]
    if title and title != default_topic:
        points.append(title)
    return points


def _resolve_local_path(request: ParseRequest) -> Path | None:
    for candidate in _candidate_local_paths(request):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _candidate_local_paths(request: ParseRequest) -> list[Path]:
    candidates: list[Path] = []

    if request.key:
        key_path = Path(request.key).expanduser()
        if key_path.is_absolute():
            candidates.append(key_path.resolve())
        else:
            candidates.append((_courseware_root() / request.key).resolve())

    if request.file_name:
        candidates.append((_courseware_root() / request.courseware_id / request.file_name).resolve())

    if request.file_path:
        legacy_path = Path(request.file_path).expanduser()
        if legacy_path.is_absolute():
            candidates.append(legacy_path.resolve())

    return candidates


def _courseware_root() -> Path:
    return _repo_root() / "backend" / "data" / "courseware"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _detect_suffix(local_path: Path, request: ParseRequest) -> str:
    if local_path.suffix:
        return local_path.suffix.lower()

    preferred_name = request.preferred_name or ""
    if Path(preferred_name).suffix:
        return Path(preferred_name).suffix.lower()

    if request.content_type == "application/pdf":
        return ".pdf"
    if request.content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        return ".pptx"
    return ""


def _best_effort_ingest(request: ParseRequest, payload: dict[str, object]) -> None:
    """Best-effort ingest for RAG retrieval.

    This keeps the parse contract unchanged while enabling "visual summary enters retrieval"
    without requiring a separate orchestration step.
    """

    try:
        from app.services.ingest_service import ingest_courseware_chunks
        from app.services.text_chunker import TextChunkerService

        segments = payload.get("segments")
        if not isinstance(segments, list) or not segments:
            return

        pages_for_chunking: list[dict[str, object]] = []
        visual_docs: list[dict[str, object]] = []

        for seg in segments:
            if not isinstance(seg, dict):
                continue
            page_index = seg.get("pageIndex")
            if not isinstance(page_index, int) or page_index <= 0:
                continue

            title = seg.get("title") if isinstance(seg.get("title"), str) else None
            content = seg.get("content") if isinstance(seg.get("content"), str) else ""
            knowledge_points = seg.get("knowledgePoints")
            if not isinstance(knowledge_points, list):
                knowledge_points = []

            visual_summary = seg.get("visualSummary") if isinstance(seg.get("visualSummary"), str) else None
            visual_objects = seg.get("visualObjects") if isinstance(seg.get("visualObjects"), list) else None
            page_image_path = seg.get("pageImagePath") if isinstance(seg.get("pageImagePath"), str) else None

            pages_for_chunking.append(
                {
                    "page_index": page_index,
                    "title": title,
                    "content": content,
                    "knowledge_points": knowledge_points,
                    "visualSummary": visual_summary,
                    "visualObjects": visual_objects,
                    "pageImagePath": page_image_path,
                }
            )

            if visual_summary:
                visual_docs.append(
                    {
                        "chunk_id": f"{request.courseware_id}_p{page_index:03d}_visual",
                        "page_index": page_index,
                        "content": f"视觉摘要：{visual_summary}",
                        "metadata": {
                            "courseware_id": request.courseware_id,
                            "page_index": page_index,
                            "source": "visual_summary",
                            "title": title,
                            "visual_summary": visual_summary,
                            "visual_objects": visual_objects,
                            "page_image_path": page_image_path,
                        },
                    }
                )

        chunker = TextChunkerService()
        chunks = chunker.chunk_courseware_pages(request.courseware_id, pages_for_chunking)
        if not chunks and not visual_docs:
            return

        ingest_courseware_chunks(request.courseware_id, [*chunks, *visual_docs])
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Parse ingest skipped. coursewareId=%s reason=%s",
            request.courseware_id,
            str(exc),
        )
