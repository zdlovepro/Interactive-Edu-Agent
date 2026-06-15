from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class PageContent(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    page_index: int = Field(..., ge=1, alias="pageIndex", description="Page number starting from 1.")
    title: str | None = Field(default=None, description="Current page title.")
    text_content: str = Field(..., min_length=1, alias="textContent", description="Current page text content.")
    keywords: List[str] = Field(default_factory=list, description="Extracted page keywords.")
    page_image_path: str | None = Field(default=None, alias="pageImagePath")
    visual_summary: str | None = Field(default=None, alias="visualSummary")
    visual_objects: List[str] = Field(default_factory=list, alias="visualObjects")


class ScriptGenerateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    courseware_id: str = Field(..., min_length=1, alias="coursewareId", description="Courseware unique id.")
    courseware_name: str = Field(..., min_length=1, alias="coursewareName", description="Courseware display name.")
    subject: str | None = Field(default=None, description="Courseware subject.")
    pages: List[PageContent] = Field(..., min_length=1, description="Ordered page content list.")


class PageScript(BaseModel):
    page_index: int = Field(..., description="Related page index.")
    script: str = Field(..., min_length=1, description="Narration script for the page.")
    transition: str = Field(default="", description="Optional transition text to the next page.")


class ScriptGenerateResponse(BaseModel):
    courseware_id: str = Field(..., description="Courseware unique id.")
    opening: str = Field(..., min_length=1, description="Opening narration.")
    pages: List[PageScript] = Field(..., min_length=1, description="Page script list.")
    closing: str = Field(..., min_length=1, description="Closing narration.")
