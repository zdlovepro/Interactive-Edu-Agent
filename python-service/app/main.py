"""
FastAPI 应用入口
================
注册路由、配置 CORS、启动日志。
遵照规约 3.2：路径前缀 /python/v1，FastAPI 自动生成 Swagger 文档（/docs）。

保存位置：python-service/app/main.py
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.services.vector_store import get_vector_store
from app.utils.logger import logger

app = FastAPI(title=settings.PROJECT_NAME)

# ---- CORS 配置（开发阶段允许所有来源，生产环境应收紧） ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 注册路由，前缀遵照规约 /python/v1 ----
from app.routers import parse
app.include_router(parse.router, prefix="/python/v1", tags=["解析服务"])

# ---- 启动事件 ----
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化向量库连接"""
    logger.info("=" * 60)
    logger.info("服务启动：%s", settings.PROJECT_NAME)
    logger.info("Swagger 文档：http://localhost:8100/docs")
    logger.info("=" * 60)
    try:
        vector_store = get_vector_store()
        logger.info("Vector database is connected and ready.")
    except Exception as e:
        logger.warning("Vector store 未就绪（不影响解析功能）：%s", e)


@app.get("/")
def read_root():
    return {"message": "Welcome to Python AI Service API"}
