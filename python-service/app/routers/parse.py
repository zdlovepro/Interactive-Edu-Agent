"""
解析路由
========
遵照规约：
- 路径前缀 /python/v1（在 main.py 中 include 时拼接）
- 统一响应格式 code / message / data
- 关键接口记录请求耗时

保存位置：python-service/app/routers/parse.py
"""

import time
from pathlib import Path

from fastapi import APIRouter, UploadFile, File

from app.schemas.parse import BaseResponse, ParseRequest
from app.services.ppt_parser import parse_pptx
from app.services.pdf_parser import parse_pdf
from app.utils.logger import logger
from app.core.config import settings

router = APIRouter(tags=["解析模块"])


# ============================================================
# 健康检查（用于 Java 后端探活 / 部署验证）
# ============================================================
@router.get("/health", summary="健康检查")
async def health_check() -> BaseResponse:
    """返回服务运行状态，用于部署探活和 Java 后端连通性验证。"""
    return BaseResponse(
        code=0,
        message="success",
        data={
            "service": settings.PROJECT_NAME,
            "status": "running",
        },
    )


# ============================================================
# 解析接口（阶段二任务 7 正式使用，阶段一已可验证）
# ============================================================
@router.post("/parse", summary="解析课件文件")
async def parse_courseware(req: ParseRequest) -> BaseResponse:
    """
    接收课件信息，根据文件后缀调用对应解析器。

    此接口由 Java 后端通过 HTTP 调用，传入课件 ID 和文件路径。
    解析完成后返回结构化的每页内容。

    Parameters
    ----------
    req : ParseRequest
        包含 courseware_id 和 file_path。

    Returns
    -------
    BaseResponse
        code=0 时 data 为 ParseResult；非 0 时 data 为 null。
    """
    start_time = time.time()
    logger.info("收到解析请求：courseware_id=%s, file_path=%s", req.courseware_id, req.file_path)

    try:
        suffix = Path(req.file_path).suffix.lower()

        if suffix == ".pptx":
            result = parse_pptx(req.file_path, req.courseware_id)
        elif suffix == ".pdf":
            result = parse_pdf(req.file_path, req.courseware_id)
        else:
            return BaseResponse(
                code=40001,
                message=f"不支持的文件格式：{suffix}，仅支持 .pptx 和 .pdf",
                data=None,
            )

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "解析成功：courseware_id=%s, 耗时=%dms",
            req.courseware_id,
            elapsed_ms,
        )

        return BaseResponse(
            code=0,
            message="success",
            data=result.model_dump(),
        )

    except FileNotFoundError as e:
        logger.error("文件未找到：%s", e)
        return BaseResponse(code=40002, message=str(e), data=None)

    except Exception as e:
        logger.exception("解析过程发生异常：%s", e)
        return BaseResponse(code=50001, message=f"解析服务内部错误：{str(e)}", data=None)


# ============================================================
# 文件上传（仅供本服务独立调试使用，正式流程由 Java 后端上传至 MinIO）
# ============================================================
@router.post("/upload-debug", summary="[调试] 上传文件到本地")
async def upload_debug(file: UploadFile = File(...)) -> BaseResponse:
    """
    调试用上传接口：将文件保存到本地 uploads/ 目录，返回保存路径。
    正式环境中文件由 Java 后端管理，此接口不参与生产流程。
    """
    import aiofiles

    upload_dir = Path(__file__).resolve().parent.parent.parent / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    save_path = upload_dir / file.filename
    async with aiofiles.open(save_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    logger.info("调试上传完成：%s（大小 %d 字节）", save_path, len(content))

    return BaseResponse(
        code=0,
        message="success",
        data={"file_path": str(save_path), "file_name": file.filename, "size": len(content)},
    )
