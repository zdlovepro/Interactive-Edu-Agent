from __future__ import annotations

from typing import Any

from app.schemas.ingest import IngestPage, IngestPagesRequest
from app.schemas.parse import ParseRequest
from app.services.ingest_service import ingest_courseware_chunks
from app.services.parse_service import parse_courseware_file
from app.services.text_chunker import TextChunkerService
from app.utils.logger import logger


def ingest_courseware_from_parse_request(
    request: ParseRequest,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    include_visual_summary_docs: bool = True,
) -> dict[str, Any]:
    payload = parse_courseware_file(request)
    segments = payload.get("segments")
    if not isinstance(segments, list):
        segments = []

    pages = [
        IngestPage(
            pageIndex=seg.get("pageIndex"),
            title=seg.get("title"),
            content=seg.get("content") or "",
            knowledgePoints=seg.get("knowledgePoints") or [],
            pageImagePath=seg.get("pageImagePath"),
            visualSummary=seg.get("visualSummary"),
            visualObjects=seg.get("visualObjects") or [],
        )
        for seg in segments
        if isinstance(seg, dict) and isinstance(seg.get("pageIndex"), int) and seg.get("pageIndex") > 0
    ]

    result = ingest_courseware_from_pages_request(
        IngestPagesRequest(
            coursewareId=request.courseware_id,
            pages=pages,
            chunkSize=chunk_size,
            chunkOverlap=chunk_overlap,
            includeVisualSummaryDocs=include_visual_summary_docs,
        )
    )
    result["pages"] = payload.get("pages")
    return result


def ingest_courseware_from_pages_request(request: IngestPagesRequest) -> dict[str, Any]:
    pages_for_chunking, visual_docs = _prepare_pages_and_visual_docs(
        request.courseware_id,
        request.pages,
        request.include_visual_summary_docs,
    )

    chunker = TextChunkerService(chunk_size=request.chunk_size, chunk_overlap=request.chunk_overlap)
    chunks = chunker.chunk_courseware_pages(request.courseware_id, pages_for_chunking)

    documents: list[dict[str, Any]] = []
    documents.extend(chunks)
    documents.extend(visual_docs)

    logger.info(
        "Prepared ingest documents. coursewareId=%s pageCount=%s chunkCount=%s visualDocCount=%s",
        request.courseware_id,
        len(pages_for_chunking),
        len(chunks),
        len(visual_docs),
    )

    result = ingest_courseware_chunks(request.courseware_id, documents)
    result.update(
        {
            "pages": len(pages_for_chunking),
            "chunk_count": len(chunks),
            "visual_doc_count": len(visual_docs),
        }
    )
    return result


def _prepare_pages_and_visual_docs(
    courseware_id: str,
    pages: list[IngestPage],
    include_visual_summary_docs: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    pages_for_chunking: list[dict[str, Any]] = []
    visual_docs: list[dict[str, Any]] = []

    for page in pages:
        visual_summary = (page.visual_summary or "").strip() or None
        page_image_path = (page.page_image_path or "").strip() or None
        title = (page.title or "").strip() or None
        content = (page.content or "").strip()
        knowledge_points = [item.strip() for item in page.knowledge_points if isinstance(item, str) and item.strip()]
        visual_objects = [item.strip() for item in page.visual_objects if isinstance(item, str) and item.strip()]

        pages_for_chunking.append(
            {
                "page_index": page.page_index,
                "title": title,
                "content": content,
                "knowledge_points": knowledge_points,
                "visualSummary": visual_summary,
                "visualObjects": visual_objects,
                "pageImagePath": page_image_path,
            }
        )

        if include_visual_summary_docs and visual_summary:
            visual_docs.append(
                {
                    "chunk_id": f"{courseware_id}_p{page.page_index:03d}_visual",
                    "page_index": page.page_index,
                    "content": f"视觉摘要：{visual_summary}",
                    "metadata": {
                        "courseware_id": courseware_id,
                        "page_index": page.page_index,
                        "source": "visual_summary",
                        "title": title,
                        "visual_summary": visual_summary,
                        "visual_objects": visual_objects,
                        "page_image_path": page_image_path,
                    },
                }
            )

    return pages_for_chunking, visual_docs
