from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import BaseResponse, success_response
from app.schemas.course_resource_import import (
    CourseResourceImportDiscoverRequest,
    CourseResourceImportDownloadRequest,
    CourseResourceImportRequest,
)
from app.services.course_resource_import_service import (
    discover_course_resources,
    download_course_resources,
    import_course_resources,
)

router = APIRouter(prefix="/course-resource-import", tags=["course-resource-import"], include_in_schema=False)


@router.post("/discover", response_model=BaseResponse, summary="Discover course resources")
async def discover_course_resource_endpoint(request: CourseResourceImportDiscoverRequest) -> BaseResponse:
    return success_response(await discover_course_resources(request))


@router.post("/download", response_model=BaseResponse, summary="Download course resources")
async def download_course_resource_endpoint(request: CourseResourceImportDownloadRequest) -> BaseResponse:
    return success_response(await download_course_resources(request))


@router.post("/import", response_model=BaseResponse, summary="Import course resources")
async def import_course_resource_endpoint(request: CourseResourceImportRequest) -> BaseResponse:
    return success_response(await import_course_resources(request))
