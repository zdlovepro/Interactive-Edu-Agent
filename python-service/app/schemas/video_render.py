from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VideoRenderSegment(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    segment_id: str | None = Field(default=None, alias="segmentId")
    page_index: int = Field(..., ge=1, alias="pageIndex")
    title: str | None = None
    script_text: str = Field(default="", alias="scriptText")
    page_image_path: str = Field(..., min_length=1, alias="pageImagePath")
    page_image_url: str | None = Field(default=None, alias="pageImageUrl")
    knowledge_points: list[str] = Field(default_factory=list, alias="knowledgePoints")
    visual_summary: str | None = Field(default=None, alias="visualSummary")
    audio_path: str | None = Field(default=None, alias="audioPath")
    audio_url: str | None = Field(default=None, alias="audioUrl")
    duration_ms: int | None = Field(default=None, alias="durationMs")


class VideoRenderRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    courseware_id: str = Field(..., min_length=1, alias="coursewareId")
    output_dir: str | None = Field(default=None, alias="outputDir")
    backend_base_url: str | None = Field(default=None, alias="backendBaseUrl")
    width: int = Field(default=1280, ge=320, le=3840)
    height: int = Field(default=720, ge=240, le=2160)
    hls_segment_seconds: int = Field(default=6, ge=1, le=60, alias="hlsSegmentSeconds")
    segments: list[VideoRenderSegment] = Field(default_factory=list)


class VideoRenderTimelineItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    segment_id: str = Field(alias="segmentId")
    page_index: int = Field(alias="pageIndex")
    title: str | None = None
    start_ms: int = Field(alias="startMs")
    end_ms: int = Field(alias="endMs")
    duration_ms: int = Field(alias="durationMs")
    page_image_path: str = Field(alias="pageImagePath")
    audio_path: str = Field(alias="audioPath")


class VideoRenderResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    courseware_id: str = Field(alias="coursewareId")
    output_dir: str = Field(alias="outputDir")
    input_manifest_path: str = Field(alias="inputManifestPath")
    timeline_path: str = Field(alias="timelinePath")
    subtitle_path: str = Field(alias="subtitlePath")
    mp4_path: str = Field(alias="mp4Path")
    hls_playlist_path: str = Field(alias="hlsPlaylistPath")
    duration_ms: int = Field(alias="durationMs")
    segment_count: int = Field(alias="segmentCount")
    timeline: list[VideoRenderTimelineItem]
