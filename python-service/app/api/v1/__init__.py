from fastapi import APIRouter

from app.api.v1.course_resource_import import router as course_resource_import_router
from app.api.v1.parse import router as parse_router
from app.api.v1.qa import router as qa_router
from app.api.v1.script import router as script_router

router = APIRouter()
router.include_router(course_resource_import_router)
router.include_router(parse_router)
router.include_router(qa_router)
router.include_router(script_router)
