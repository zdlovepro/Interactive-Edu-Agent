from __future__ import annotations

from typing import Any

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
    """End-to-end ingest pipeline.

    Flow:
    - Parse courseware (same as /parse)
    - Chunk page text into documents, carrying visual_summary metadata
    - Optionally add one extra document per page for visual summary itself
    - Ingest into vector store
    """

    payload = parse_courseware_file(request)
    segments = payload.get("segments")
    if not isinstance(segments, list):
        segments = []

    pages_for_chunking: list[dict[str, Any]] = []
    visual_docs: list[dict[str, Any]] = []

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

        if include_visual_summary_docs and visual_summary:
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

    chunker = TextChunkerService(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
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
            "pages": payload.get("pages"),
            "chunk_count": len(chunks),
            "visual_doc_count": len(visual_docs),
        }
    )
    return result
