from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import BaseResponse, success_response
from app.schemas.video_render import VideoRenderRequest
from app.services.video_render_service import render_courseware_video

router = APIRouter(prefix="/video-render", tags=["video-render"], include_in_schema=False)


@router.post("/render", response_model=BaseResponse, summary="Render courseware lecture video")
async def render_courseware_video_endpoint(request: VideoRenderRequest) -> BaseResponse:
    return success_response(render_courseware_video(request))
