from fastapi import APIRouter

from app.api.v1.chaoxing_import import router as chaoxing_import_router
from app.api.v1.course_resource_import import router as course_resource_import_router
from app.api.v1.digital_human import router as digital_human_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.parse import router as parse_router
from app.api.v1.qa import router as qa_router
from app.api.v1.rag import router as rag_router
from app.api.v1.script import router as script_router

router = APIRouter()
router.include_router(chaoxing_import_router)
router.include_router(course_resource_import_router)
router.include_router(digital_human_router)
router.include_router(ingest_router)
router.include_router(parse_router)
router.include_router(qa_router)
router.include_router(rag_router)
router.include_router(script_router)
