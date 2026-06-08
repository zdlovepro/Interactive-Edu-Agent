"""
统一配置
========
保存位置：python-service/app/core/config.py
"""

from pydantic import AliasChoices, Field
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
    EMBEDDING_PROVIDER: str = "dashscope"
    EMBEDDING_API_KEY: str | None = None
    DASHSCOPE_API_KEY: str | None = None
    EMBEDDING_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_MODEL_NAME: str = "text-embedding-v4"
    EMBEDDING_DIM_SIZE: int = 1024

    # ---------- LLM Config ----------
    LLM_API_KEY: str = Field(default="", validation_alias=AliasChoices("LLM_API_KEY", "DEEPSEEK_API_KEY"))
    LLM_API_BASE: str = Field(
        default="https://api.deepseek.com",
        validation_alias=AliasChoices("LLM_API_BASE", "DEEPSEEK_API_BASE"),
    )
    LLM_MODEL_NAME: str = Field(
        default="deepseek-v4-pro",
        validation_alias=AliasChoices("LLM_MODEL_NAME", "DEEPSEEK_MODEL_NAME"),
    )
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT: int = 120
    LLM_REASONING_EFFORT: str = Field(
        default="high",
        validation_alias=AliasChoices("LLM_REASONING_EFFORT", "DEEPSEEK_REASONING_EFFORT"),
    )
    LLM_ENABLE_THINKING: bool = Field(
        default=True,
        validation_alias=AliasChoices("LLM_ENABLE_THINKING", "DEEPSEEK_ENABLE_THINKING"),
    )

    # ---------- Vision Model Config (Optional) ----------
    VISION_API_KEY: str = Field(default="", validation_alias=AliasChoices("VISION_API_KEY", "VISION_KEY"))
    VISION_API_BASE: str = Field(
        default="",
        validation_alias=AliasChoices("VISION_API_BASE", "VISION_BASE"),
    )
    VISION_MODEL_NAME: str = Field(
        default="",
        validation_alias=AliasChoices("VISION_MODEL_NAME", "VISION_MODEL"),
    )
    VISION_TEMPERATURE: float = 0.2
    VISION_MAX_TOKENS: int = 512
    VISION_TIMEOUT: int = 120

    # ---------- Redis / Chaoxing authorized import ----------
    REDIS_URL: str = ""
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DATABASE: int = 0
    REDIS_PASSWORD: str = ""
    CHAOXING_AUTH_TTL_SECONDS: int = 7200
    CHAOXING_AUTH_LOGIN_URL: str = "https://passport2.chaoxing.com/login?refer=https%3A%2F%2Fi.chaoxing.com"
    CHAOXING_AUTH_HEADLESS: bool = True
    CHAOXING_AUTH_TIMEOUT_SECONDS: int = 180
    CHAOXING_MAX_CHAPTERS: int = 120
    CHAOXING_MAX_CARDS_PER_CHAPTER: int = 80

    # ---------- Object storage for full mode parsing ----------
    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "courseware"
    MINIO_SECURE: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
