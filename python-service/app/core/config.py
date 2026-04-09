"""
统一配置
========
保存位置：python-service/app/core/config.py
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Interactive Lecture API"

    # ---------- Vector DB Config (Milvus) ----------
    MILVUS_URI: str = "http://localhost:19530"
    MILVUS_USER: str = ""
    MILVUS_PASSWORD: str = ""
    MILVUS_DB_NAME: str = "default"
    COLLECTION_NAME: str = "lecture_knowledge"

    # ---------- Embedding Model Config ----------
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-large-zh-v1.5"
    EMBEDDING_DIM_SIZE: int = 1024

    # ---------- 解析服务相关 ----------
    MAX_UPLOAD_SIZE_MB: int = 50          # 上传文件大小上限
    PARSE_TIMEOUT_SECONDS: int = 120      # 解析超时时间（POS要求≤2min）

    class Config:
        env_file = ".env"


settings = Settings()
