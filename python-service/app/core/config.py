"""
统一配置
========
保存位置：python-service/app/core/config.py
"""

from pydantic import AliasChoices, Field, model_validator
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

    # ---------- Chaoxing Real Import Test Config ----------
    CHAOXING_COURSE_URL: str = Field(default="", validation_alias=AliasChoices("CHAOXING_COURSE_URL", "CHAOSTAR_COURSE_URL"))
    CHAOXING_COURSE_ID: str = Field(default="", validation_alias=AliasChoices("CHAOXING_COURSE_ID", "CHAOSTAR_COURSE_ID"))
    CHAOXING_CLAZZ_ID: str = Field(default="", validation_alias=AliasChoices("CHAOXING_CLAZZ_ID", "CHAOSTAR_CLAZZ_ID"))
    CHAOXING_CPI: str = Field(default="", validation_alias=AliasChoices("CHAOXING_CPI", "CHAOSTAR_CPI"))
    CHAOXING_ENC: str = Field(default="", validation_alias=AliasChoices("CHAOXING_ENC", "CHAOSTAR_ENC"))
    CHAOXING_T: str = Field(default="", validation_alias=AliasChoices("CHAOXING_T", "CHAOSTAR_T"))
    CHAOXING_COOKIE: str = Field(default="", validation_alias=AliasChoices("CHAOXING_COOKIE", "CHAOSTAR_COOKIE"))
    CHAOXING_AUTHORIZATION: str = Field(
        default="",
        validation_alias=AliasChoices("CHAOXING_AUTHORIZATION", "CHAOSTAR_AUTHORIZATION"),
    )
    CHAOXING_USER_AGENT: str = Field(default="", validation_alias=AliasChoices("CHAOXING_USER_AGENT", "CHAOSTAR_USER_AGENT"))

    # CLI aliases used by app.course_resource_importer.cli.
    RESOURCE_COOKIE: str = ""
    RESOURCE_AUTHORIZATION: str = ""
    RESOURCE_REFERER: str = ""
    RESOURCE_USER_AGENT: str = ""
    RESOURCE_OUTPUT_DIR: str = "./data/chaoxing-real-test"

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
    VISION_ENABLED: bool = False
    VISION_PROVIDER: str = "qwen-vl"
    VISION_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("VISION_API_KEY", "DASHSCOPE_API_KEY", "VISION_KEY"),
    )
    VISION_API_BASE: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias=AliasChoices("VISION_API_BASE", "VISION_BASE_URL", "VISION_BASE"),
    )
    VISION_MODEL_NAME: str = Field(
        default="qwen3-vl-plus",
        validation_alias=AliasChoices("VISION_MODEL_NAME", "VISION_MODEL"),
    )
    VISION_TEMPERATURE: float = 0.2
    VISION_MAX_TOKENS: int = 512
    VISION_TIMEOUT: int = 120
    VISION_MAX_IMAGE_BYTES: int = 7 * 1024 * 1024
    VISION_TRUST_ENV_PROXY: bool = False

    @model_validator(mode="after")
    def normalize_api_key_aliases(self) -> "Settings":
        if not (self.VISION_API_KEY or "").strip():
            self.VISION_API_KEY = (self.DASHSCOPE_API_KEY or self.EMBEDDING_API_KEY or "").strip()
        if not (self.EMBEDDING_API_KEY or "").strip() and (self.DASHSCOPE_API_KEY or "").strip():
            self.EMBEDDING_API_KEY = self.DASHSCOPE_API_KEY
        return self

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
