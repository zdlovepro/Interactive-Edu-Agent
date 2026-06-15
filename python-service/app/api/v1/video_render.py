from __future__ import annotations

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from app.schemas.common import BaseResponse, success_response
from app.schemas.video_render import VideoRenderRequest
from app.services.video_render_service import render_courseware_video

router = APIRouter(prefix="/video-render", tags=["video-render"], include_in_schema=False)


@router.post("/render", response_model=BaseResponse, summary="Render courseware lecture video")
async def render_courseware_video_endpoint(request: VideoRenderRequest) -> BaseResponse:
    result = await run_in_threadpool(render_courseware_video, request)
    return success_response(result)
