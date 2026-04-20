import logging
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from app.services.demo_edu import build_parse_payload

logger = logging.getLogger(__name__)
from app.api.v1 import script as script_router

app = FastAPI(title="AI Interactive Lecture - Python Service")

@app.on_event("startup")
async def startup_event():
    # Application startup: Initialize vector store connection
    try:
        # 建立数据库连接，首次启动可能下载权重模型（如果使用本地 embedding）
        vector_store = get_vector_store()
        print("Vector database is connected and ready.")
    except Exception as e:
        print(f"Error starting vector store dependency: {e}")

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
