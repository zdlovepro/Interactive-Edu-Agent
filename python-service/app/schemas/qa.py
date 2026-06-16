from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class QaCoursewarePage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    page_index: int = Field(..., ge=1, alias="pageIndex")
    title: str | None = None
    content: str | None = None
    knowledge_points: list[str] = Field(default_factory=list, alias="knowledgePoints")
    visual_summary: str | None = Field(default=None, alias="visualSummary")
    visual_objects: list[str] = Field(default_factory=list, alias="visualObjects")


class QaAskTextRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    session_id: str = Field(..., min_length=1, alias="sessionId")
    courseware_id: str = Field(..., min_length=1, alias="coursewareId")
    page_index: int | None = Field(default=None, ge=1, alias="pageIndex")
    question: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=10, alias="topK")
    current_page_title: str | None = Field(default=None, alias="currentPageTitle")
    current_page_content: str | None = Field(default=None, alias="currentPageContent")
    current_page_image_path: str | None = Field(default=None, alias="currentPageImagePath")
    current_page_visual_summary: str | None = Field(default=None, alias="currentPageVisualSummary")
    current_page_knowledge_points: list[str] = Field(default_factory=list, alias="currentPageKnowledgePoints")
    current_page_visual_objects: list[str] = Field(default_factory=list, alias="currentPageVisualObjects")
    courseware_pages: list[QaCoursewarePage] = Field(default_factory=list, alias="coursewarePages")


class QaEvidenceItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    source: str
    text: str
    page_index: int | None = Field(default=None, alias="pageIndex")
    chunk_id: str | None = Field(default=None, alias="chunkId")


class QaAskTextResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    answer: str = Field(..., min_length=1)
    evidence: list[QaEvidenceItem] = Field(default_factory=list)
    latency_ms: int = Field(..., ge=0, alias="latencyMs")
