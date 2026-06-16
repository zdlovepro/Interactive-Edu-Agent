from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.parse import ParseRequest


class IngestRequest(ParseRequest):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    chunk_size: int = Field(default=500, ge=100, le=2000, alias="chunkSize")
    chunk_overlap: int = Field(default=50, ge=0, le=500, alias="chunkOverlap")
    include_visual_summary_docs: bool = Field(default=True, alias="includeVisualSummaryDocs")


class IngestPage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    page_index: int = Field(..., ge=1, alias="pageIndex")
    title: str | None = None
    content: str = ""
    knowledge_points: list[str] = Field(default_factory=list, alias="knowledgePoints")
    page_image_path: str | None = Field(default=None, alias="pageImagePath")
    visual_summary: str | None = Field(default=None, alias="visualSummary")
    visual_objects: list[str] = Field(default_factory=list, alias="visualObjects")


class IngestPagesRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    courseware_id: str = Field(..., min_length=1, alias="coursewareId")
    pages: list[IngestPage] = Field(default_factory=list)
    chunk_size: int = Field(default=500, ge=100, le=2000, alias="chunkSize")
    chunk_overlap: int = Field(default=50, ge=0, le=500, alias="chunkOverlap")
    include_visual_summary_docs: bool = Field(default=True, alias="includeVisualSummaryDocs")
