from __future__ import annotations

from pydantic import ConfigDict, Field

from app.schemas.parse import ParseRequest


class IngestRequest(ParseRequest):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    chunk_size: int = Field(default=500, ge=100, le=2000, alias="chunkSize")
    chunk_overlap: int = Field(default=50, ge=0, le=500, alias="chunkOverlap")
    include_visual_summary_docs: bool = Field(default=True, alias="includeVisualSummaryDocs")
