from __future__ import annotations

from fastapi import APIRouter

from app.schemas.chaoxing_import_task import ChaoxingImportTaskCreateRequest
from app.schemas.common import BaseResponse, success_response
from app.services.chaoxing_import_task_service import (
    create_chaoxing_import_task,
    get_chaoxing_import_manifest,
    get_chaoxing_import_task,
)

router = APIRouter(prefix="/import/chaoxing", tags=["chaoxing-import"])


@router.post("/tasks", response_model=BaseResponse, summary="Create Chaoxing import task")
async def create_chaoxing_import_task_endpoint(request: ChaoxingImportTaskCreateRequest) -> BaseResponse:
    return success_response(await create_chaoxing_import_task(request))


@router.get("/tasks/{task_id}", response_model=BaseResponse, summary="Get Chaoxing import task")
def get_chaoxing_import_task_endpoint(task_id: str) -> BaseResponse:
    return success_response(get_chaoxing_import_task(task_id))


@router.get("/tasks/{task_id}/manifest", response_model=BaseResponse, summary="Get Chaoxing import manifest")
def get_chaoxing_import_manifest_endpoint(task_id: str) -> BaseResponse:
    return success_response(get_chaoxing_import_manifest(task_id))
