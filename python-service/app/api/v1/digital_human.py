from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import BaseResponse, success_response
from app.schemas.digital_human import AudioDriveGenerateRequest
from app.services.audio_drive_service import generate_audio_drive_protocol
from app.utils.logger import logger

router = APIRouter(prefix="/digital-human", tags=["digital-human"])


@router.post("/audio-drive", response_model=BaseResponse, summary="Generate audio timeline and digital-human drive protocol")
async def generate_audio_drive_endpoint(request: AudioDriveGenerateRequest) -> BaseResponse:
    logger.info(
        "Audio drive request received. coursewareId=%s pageIndex=%s format=%s",
        request.courseware_id,
        request.page_index,
        request.protocol_format,
    )
    result = generate_audio_drive_protocol(request)
    return success_response(result.model_dump(by_alias=True))
