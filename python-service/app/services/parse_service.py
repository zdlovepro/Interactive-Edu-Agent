from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from app.core.config import settings
from app.core.exceptions import AppException, BUSINESS_VALIDATION_FAILED, PARAM_ERROR, PythonServiceException
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
        return _parse_and_build_payload(local_path, request)

    if request.normalized_storage == "minio":
        temp_dir: Path | None = None
        try:
            temp_dir, local_path = _download_minio_object(request)
            return _parse_and_build_payload(local_path, request)
        finally:
            if temp_dir is not None:
                shutil.rmtree(temp_dir, ignore_errors=True)

    raise AppException(PARAM_ERROR, f"unsupported storage: {request.storage}")


def _parse_and_build_payload(local_path: Path, request: ParseRequest) -> dict[str, object]:
    try:
        result = _parse_local_file(local_path, request)
    except FileNotFoundError as exc:
        raise AppException(BUSINESS_VALIDATION_FAILED, str(exc)) from exc
    except ValueError as exc:
        raise AppException(PARAM_ERROR, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Courseware parse failed. coursewareId=%s path=%s", request.courseware_id, local_path)
        raise PythonServiceException("courseware parse failed") from exc

    visual_summary_by_page: dict[int, object] = {}
    page_images: dict[int, str] = {}
    try:
        from app.services.visual_summary_service import generate_visual_summaries

        summaries, rendered_images = generate_visual_summaries(
            parse_result=result,
            source_path=local_path,
            output_dir=_render_root() / request.courseware_id / "visual" / "pages",
        )
        visual_summary_by_page = {item.page_index: item for item in summaries}
        page_images = rendered_images
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Visual summary generation skipped. coursewareId=%s reason=%s",
            request.courseware_id,
            str(exc),
        )

    payload = _build_contract_payload(
        result,
        request.preferred_name,
        visual_summary_by_page=visual_summary_by_page,
        page_images=page_images,
    )

    _best_effort_ingest(request, payload)
    return payload


def _download_minio_object(request: ParseRequest) -> tuple[Path, Path]:
    if not request.key:
        raise AppException(PARAM_ERROR, "minio parse requires key")
    if not settings.MINIO_ACCESS_KEY or not settings.MINIO_SECRET_KEY:
        raise AppException(BUSINESS_VALIDATION_FAILED, "minio credentials are not configured")

    try:
        from minio import Minio
    except ImportError as exc:  # pragma: no cover - dependency exists in full image.
        raise PythonServiceException("minio dependency is not installed") from exc

    endpoint = settings.MINIO_ENDPOINT.strip()
    parsed = urlsplit(endpoint if "://" in endpoint else f"http://{endpoint}")
    minio_endpoint = parsed.netloc or parsed.path
    secure = settings.MINIO_SECURE or parsed.scheme == "https"
    bucket = settings.MINIO_BUCKET
    object_key = request.key.strip().lstrip("/")

    temp_dir = Path(tempfile.mkdtemp(prefix=f"courseware_{request.courseware_id}_"))
    filename = _safe_filename(request.preferred_name or Path(object_key).name or f"{request.courseware_id}.bin")
    local_path = temp_dir / filename

    try:
        client = Minio(
            minio_endpoint,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=secure,
        )
        client.fget_object(bucket, object_key, str(local_path))
        logger.info(
            "Downloaded MinIO courseware object for parse. coursewareId=%s bucket=%s key=%s bytes=%s",
            request.courseware_id,
            bucket,
            object_key,
            local_path.stat().st_size if local_path.exists() else 0,
        )
        return temp_dir, local_path
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.exception(
            "Failed to download MinIO courseware object. coursewareId=%s bucket=%s key=%s",
            request.courseware_id,
            bucket,
            object_key,
        )
        raise AppException(BUSINESS_VALIDATION_FAILED, f"minio courseware file not found: {object_key}") from exc


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
    default_topic = Path(preferred_name or result.courseware_id).stem or result.courseware_id

    visual_summary_by_page = visual_summary_by_page or {}
    page_images = page_images or {}

    for page in result.pages:
        title = _derive_title(page, default_topic)
        content = _merge_page_content(page)
        visual_summary_item = visual_summary_by_page.get(page.page_index)
        outline.append(title)
        segment: dict[str, object] = {
            "pageIndex": page.page_index,
            "title": title,
            "content": content,
            "knowledgePoints": _derive_knowledge_points(title, default_topic),
        }

        if visual_summary_item is not None:
            segment["visualSummary"] = getattr(visual_summary_item, "visual_summary", None)
            segment["visualObjects"] = getattr(visual_summary_item, "objects", None)

        if page.page_index in page_images:
            segment["pageImagePath"] = page_images.get(page.page_index)

        segments.append(segment)

    return {"pages": result.total_pages, "outline": outline, "segments": segments}


def _derive_title(page, default_topic: str) -> str:
    first_line = next((line.strip() for line in page.text.splitlines() if line.strip()), "")
    if first_line:
        return first_line[:48]
    if page.notes:
        note_line = next((line.strip() for line in page.notes.splitlines() if line.strip()), "")
        if note_line:
            return note_line[:48]
    return f"{default_topic}-page-{page.page_index}"


def _merge_page_content(page) -> str:
    parts = [part.strip() for part in (page.text, page.notes) if part and part.strip()]
    if parts:
        return "\n".join(parts)
    return f"Page {page.page_index} has no extractable text."


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


def _render_root() -> Path:
    return Path(settings.RENDER_BASE_DIR).expanduser().resolve()


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


def _safe_filename(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in value)
    return safe.strip("._") or "courseware.bin"


def _best_effort_ingest(request: ParseRequest, payload: dict[str, object]) -> None:
    """Best-effort ingest for RAG retrieval.

    This keeps the parse contract unchanged while enabling retrieval without
    requiring a separate orchestration step.
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
                        "content": f"Visual summary: {visual_summary}",
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
