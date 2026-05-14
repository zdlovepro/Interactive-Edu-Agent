from __future__ import annotations

from pydantic import BaseModel, Field


class VisualSummary(BaseModel):
    page_index: int = Field(..., ge=1, description="1-based page index")
    visual_summary: str = Field(..., min_length=1, description="Short visual description for the page")
    objects: list[str] = Field(default_factory=list, description="Detected visual objects, e.g. 图表/表格/流程图")
