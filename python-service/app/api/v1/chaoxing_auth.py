from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from app.schemas.chaoxing_auth import ChaoxingAuthSessionCreateRequest
from app.schemas.common import BaseResponse, success_response
from app.services.chaoxing_auth_service import chaoxing_auth_service

router = APIRouter(prefix="/chaoxing/auth/sessions", tags=["chaoxing-auth"], include_in_schema=False)


@router.post("", response_model=BaseResponse, summary="Create Chaoxing QR auth session")
async def create_chaoxing_auth_session(request: ChaoxingAuthSessionCreateRequest) -> BaseResponse:
    payload = await chaoxing_auth_service.create_session(
        course_url=request.course_url,
        user_agent=request.user_agent,
    )
    return success_response(payload)


@router.get("/{session_id}", response_model=BaseResponse, summary="Get Chaoxing QR auth session")
async def get_chaoxing_auth_session(session_id: str) -> BaseResponse:
    return success_response(await chaoxing_auth_service.get_session(session_id))


@router.get("/{session_id}/qrcode", summary="Get Chaoxing QR auth image")
async def get_chaoxing_auth_qrcode(session_id: str) -> Response:
    image = await chaoxing_auth_service.get_qrcode(session_id)
    return Response(
        content=image,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


@router.delete("/{session_id}", response_model=BaseResponse, summary="Close Chaoxing QR auth session")
async def close_chaoxing_auth_session(session_id: str) -> BaseResponse:
    return success_response(await chaoxing_auth_service.close_session(session_id))
