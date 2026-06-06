from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class _ConfiguredModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class RagAskRequest(_ConfiguredModel):
    session_id: str = Field("rag_session", validation_alias=AliasChoices("session_id", "sessionId"))
    courseware_id: str = Field(..., min_length=1, validation_alias=AliasChoices("courseware_id", "coursewareId"))
    page_index: int | None = Field(None, ge=1, validation_alias=AliasChoices("page_index", "pageIndex", "pageNo"))
    question: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=10, validation_alias=AliasChoices("top_k", "topK"))


class RagVisualAskRequest(_ConfiguredModel):
    courseware_id: str = Field(..., min_length=1, validation_alias=AliasChoices("courseware_id", "coursewareId"))
    page_no: int = Field(..., ge=1, validation_alias=AliasChoices("page_no", "pageNo", "pageIndex"))
    question: str = Field(..., min_length=1)
    page_image_url: str | None = Field(None, validation_alias=AliasChoices("page_image_url", "pageImageUrl"))
    page_text: str = Field("", validation_alias=AliasChoices("page_text", "pageText"))
    visual_summary: str = Field("", validation_alias=AliasChoices("visual_summary", "visualSummary"))
