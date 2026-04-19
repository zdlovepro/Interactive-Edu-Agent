import logging
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from app.services.demo_edu import build_parse_payload

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Interactive Lecture - Python Service")


class ParseRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    courseware_id: str = Field(..., alias="coursewareId", description="课件唯一标识")
    storage: str | None = Field(default=None, description="存储类型，如 local/minio")
    key: str | None = Field(default=None, description="对象存储 key 或本地相对路径")
    file_name: str | None = Field(default=None, alias="fileName", description="文件名")
    content_type: str | None = Field(default=None, alias="contentType", description="文件 MIME 类型")
    file_url: str | None = Field(default=None, alias="fileUrl", description="兼容文档里的 fileUrl")


def success(data: Any) -> dict[str, Any]:
    return {"code": 0, "message": "success", "data": data}


@app.on_event("startup")
async def startup_event() -> None:
    try:
        from app.services.vector_store import get_vector_store

        get_vector_store()
        logger.info("Vector store dependency is ready.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vector store is unavailable in current environment: %s", exc)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to Python AI Service API"}


@app.get("/python/v1/health")
def health() -> dict[str, str]:
    return {"status": "UP"}


@app.post("/python/v1/parse")
def parse_courseware(request: ParseRequest) -> dict[str, Any]:
    payload = build_parse_payload(
        courseware_id=request.courseware_id,
        file_name=request.file_name,
        content_type=request.content_type,
    )
    return success(payload)
