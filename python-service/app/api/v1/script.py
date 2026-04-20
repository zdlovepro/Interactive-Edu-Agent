"""
讲稿生成路由 —— /python/v1/script
"""
import logging
from fastapi import APIRouter
from app.schemas.script import ScriptGenerateRequest, ScriptGenerateResult
from app.services.script_service import generate_script

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/script", tags=["讲稿生成"])


@router.post(
    "/generate",
    response_model=ScriptGenerateResult,
    summary="生成结构化讲稿",
    description=(
        "根据课件解析结果，调用大模型生成包含开场白、各页讲解、过渡语和结语的完整口语化讲稿。\n\n"
        "由 Java 后端在课件解析完成（状态 PARSED）后调用，结果用于驱动后续 TTS 合成流程。"
    ),
)
def generate_script_endpoint(request: ScriptGenerateRequest) -> ScriptGenerateResult:
    logger.info("收到讲稿生成请求 | courseware_id=%s", request.courseware_id)
    result = generate_script(request)
    return ScriptGenerateResult(**result)
