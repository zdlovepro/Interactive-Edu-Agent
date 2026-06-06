from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class _ConfiguredModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class ChaoxingImportTaskCreateRequest(_ConfiguredModel):
    source_type: str = Field("CHAOXING_COURSE", validation_alias=AliasChoices("source_type", "sourceType"))
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
    output_dir: str | None = Field(None, validation_alias=AliasChoices("output_dir", "outputDir"))
    build_pdf: bool = Field(True, validation_alias=AliasChoices("build_pdf", "buildPdf"))

    @property
    def output_path(self) -> Path | None:
        if not self.output_dir:
            return None
        return Path(self.output_dir).expanduser().resolve()


class ChaoxingManifestResource(_ConfiguredModel):
    resource_id: str = Field(..., alias="resourceId")
    title: str
    type: str
    source_url: str | None = Field(None, alias="sourceUrl")
    local_path: str | None = Field(None, alias="localPath")
    sha256: str | None = None
    size: int | None = None
    parse_ready: bool = Field(False, alias="parseReady")


class ChaoxingImportManifest(_ConfiguredModel):
    task_id: str = Field(..., alias="taskId")
    status: Literal["PENDING", "RUNNING", "SUCCESS", "FAILED"] = "SUCCESS"
    course_id: str | None = Field(None, alias="courseId")
    clazz_id: str | None = Field(None, alias="clazzId")
    resources: list[ChaoxingManifestResource] = Field(default_factory=list)


class ChaoxingImportTaskView(_ConfiguredModel):
    task_id: str = Field(..., alias="taskId")
    status: Literal["PENDING", "RUNNING", "SUCCESS", "FAILED"]
    progress: int = Field(..., ge=0, le=100)
    message: str
    manifest_path: str | None = Field(None, alias="manifestPath")
    manifest: ChaoxingImportManifest | None = None
