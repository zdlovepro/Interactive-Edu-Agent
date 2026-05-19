from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import BaseResponse, success_response
from app.schemas.ingest import IngestRequest
from app.services.courseware_ingest_service import ingest_courseware_from_parse_request

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=BaseResponse)
def ingest_courseware(request: IngestRequest) -> BaseResponse:
    result = ingest_courseware_from_parse_request(
        request=request,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
        include_visual_summary_docs=request.include_visual_summary_docs,
    )
    return success_response(result)
