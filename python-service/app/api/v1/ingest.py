from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import BaseResponse, success_response
from app.schemas.ingest import IngestPagesRequest, IngestRequest
from app.services.courseware_ingest_service import (
    ingest_courseware_from_pages_request,
    ingest_courseware_from_parse_request,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=BaseResponse)
def ingest_courseware(request: IngestRequest) -> BaseResponse:
    result = ingest_courseware_from_parse_request(
        request=request,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
        include_visual_summary_docs=request.include_visual_summary_docs,
    )
    return success_response(result)


@router.post("/pages", response_model=BaseResponse)
def ingest_courseware_pages(request: IngestPagesRequest) -> BaseResponse:
    return success_response(ingest_courseware_from_pages_request(request))
