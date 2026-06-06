from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.course_resource_importer.resource_models import DiscoveredResource


class _ConfiguredModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class CourseResourceImportHeaders(_ConfiguredModel):
    cookie: str | None = None
    authorization: str | None = None
    referer: str | None = None
    user_agent: str | None = Field(None, validation_alias=AliasChoices("user_agent", "userAgent"))


class DiscoveredResourcePayload(_ConfiguredModel):
    resource_id: str = Field(..., validation_alias=AliasChoices("resource_id", "resourceId"))
    platform: str = "chaoxing"
    source_type: Literal["html", "json", "js", "api"] = Field(
        "html",
        validation_alias=AliasChoices("source_type", "sourceType"),
    )
    source_url: str | None = Field(None, validation_alias=AliasChoices("source_url", "sourceUrl"))
    url: str
    title: str | None = None
    file_name: str = Field("", validation_alias=AliasChoices("file_name", "fileName"))
    extension: str = ""
    mime_type: str | None = Field(None, validation_alias=AliasChoices("mime_type", "mimeType"))
    courseid: str | None = None
    clazzid: str | None = None
    chapter_id: str | None = Field(None, validation_alias=AliasChoices("chapter_id", "chapterId"))
    object_id: str | None = Field(None, validation_alias=AliasChoices("object_id", "objectId"))
    expected_size: int | None = Field(None, validation_alias=AliasChoices("expected_size", "expectedSize"))
    expected_md5: str | None = Field(None, validation_alias=AliasChoices("expected_md5", "expectedMd5"))
    resource_kind: Literal[
        "slide_image",
        "courseware_file",
        "attachment",
        "content_image",
        "metadata",
        "ui_asset",
        "unknown",
    ] = Field("unknown", validation_alias=AliasChoices("resource_kind", "resourceKind"))
    confidence: float = 0.0
    reason: str = ""
    raw_context: dict = Field(default_factory=dict, validation_alias=AliasChoices("raw_context", "rawContext"))

    def to_resource(self) -> DiscoveredResource:
        return DiscoveredResource(**self.model_dump())

    @classmethod
    def from_resource(cls, resource: DiscoveredResource) -> "DiscoveredResourcePayload":
        return cls.model_validate(asdict(resource))


class CourseResourceImportSourceRequest(_ConfiguredModel):
    source_type: str = Field(..., validation_alias=AliasChoices("source_type", "sourceType"))
    url: str | None = Field(None, validation_alias=AliasChoices("url", "courseUrl"))
    courseid: str | None = Field(None, validation_alias=AliasChoices("courseid", "courseId"))
    clazzid: str | None = Field(None, validation_alias=AliasChoices("clazzid", "clazzId"))
    cpi: str | None = None
    enc: str | None = None
    t: str | None = None
    cookie: str | None = None
    authorization: str | None = None
    referer: str | None = None
    user_agent: str | None = Field(None, validation_alias=AliasChoices("user_agent", "userAgent"))


class CourseResourceImportDiscoverRequest(CourseResourceImportSourceRequest):
    pass


class CourseResourceImportDownloadRequest(_ConfiguredModel):
    task_id: str = Field(..., validation_alias=AliasChoices("task_id", "taskId"))
    resources: list[DiscoveredResourcePayload] = Field(default_factory=list)
    headers: CourseResourceImportHeaders = Field(default_factory=CourseResourceImportHeaders)
    output_dir: str = Field(..., validation_alias=AliasChoices("output_dir", "outputDir"))
    build_pdf: bool = Field(False, validation_alias=AliasChoices("build_pdf", "buildPdf"))

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir).expanduser().resolve()


class CourseResourceImportRequest(CourseResourceImportSourceRequest):
    output_dir: str = Field(..., validation_alias=AliasChoices("output_dir", "outputDir"))
    build_pdf: bool = Field(False, validation_alias=AliasChoices("build_pdf", "buildPdf"))

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir).expanduser().resolve()
