from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class AudioDriveGenerateRequest(BaseModel):
    """Request model for generating an audio timeline and avatar drive protocol.

    The Java backend may call this internal endpoint after TTS has produced page-level
    audio. In real deployment the most accurate mode is to pass ``audioPath`` for a
    local WAV file that the Python service can read. ``audioDurationMs`` is accepted
    as a deterministic fallback for integration tests or early-stage vendor mocking.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    courseware_id: str = Field(..., min_length=1, alias="coursewareId", description="课件唯一标识")
    page_index: int | None = Field(default=None, ge=1, alias="pageIndex", description="页码，从 1 开始")
    script_text: str = Field(..., min_length=1, alias="scriptText", description="该页用于 TTS 的讲稿文本")
    audio_path: str | None = Field(default=None, alias="audioPath", description="Python 服务可访问的本地 WAV 音频路径")
    audio_url: str | None = Field(default=None, alias="audioUrl", description="TTS 音频 URL，仅用于协议元信息透传")
    audio_duration_ms: int | None = Field(default=None, gt=0, alias="audioDurationMs", description="音频时长毫秒兜底值")
    frame_interval_ms: int = Field(default=40, ge=20, le=200, alias="frameIntervalMs", description="动作帧间隔毫秒")
    protocol_format: Literal["json", "xml", "both"] = Field(default="json", alias="protocolFormat", description="协议输出格式")
    avatar_id: str = Field(default="default-avatar", min_length=1, alias="avatarId", description="数字人形象标识")
    sdk_version: str = Field(default="vendor-neutral-v1", min_length=1, alias="sdkVersion", description="驱动协议版本")

    @model_validator(mode="after")
    def validate_audio_source(self) -> "AudioDriveGenerateRequest":
        if not self.audio_path and not self.audio_duration_ms:
            raise ValueError("audioPath 或 audioDurationMs 至少需要提供一个")
        return self


class AudioMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    duration_ms: int = Field(..., alias="durationMs", description="音频总时长，毫秒")
    sample_rate: int | None = Field(default=None, alias="sampleRate", description="采样率，Hz")
    channels: int | None = Field(default=None, description="声道数")
    source: Literal["wav", "duration-only"] = Field(..., description="音频元信息来源")


class PhonemeSegment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    start_ms: int = Field(..., ge=0, alias="startMs", description="音素片段开始时间，毫秒")
    end_ms: int = Field(..., ge=0, alias="endMs", description="音素片段结束时间，毫秒")
    phoneme: str = Field(..., min_length=1, description="归一化音素标签")
    viseme: str = Field(..., min_length=1, description="口型标签")
    energy: float = Field(..., ge=0.0, le=1.0, description="该片段归一化音量能量")
    confidence: float = Field(..., ge=0.0, le=1.0, description="音素识别/估计置信度")


class TokenTimelineItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    token_index: int = Field(..., ge=0, alias="tokenIndex", description="词元序号，从 0 开始")
    token: str = Field(..., min_length=1, description="讲稿词元")
    start_ms: int = Field(..., ge=0, alias="startMs", description="词元开始时间，毫秒")
    end_ms: int = Field(..., ge=0, alias="endMs", description="词元结束时间，毫秒")
    phoneme: str = Field(..., min_length=1, description="词元主音素标签")
    viseme: str = Field(..., min_length=1, description="词元主口型标签")


class ActionFrame(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    time_ms: int = Field(..., ge=0, alias="timeMs", description="帧时间戳，毫秒")
    phoneme: str = Field(..., min_length=1, description="当前帧主音素")
    viseme: str = Field(..., min_length=1, description="当前帧口型")
    mouth_open: float = Field(..., ge=0.0, le=1.0, alias="mouthOpen", description="嘴部张开程度")
    jaw_open: float = Field(..., ge=0.0, le=1.0, alias="jawOpen", description="下颌张开程度")
    lip_wide: float = Field(..., ge=0.0, le=1.0, alias="lipWide", description="嘴角横向拉伸程度")
    lip_round: float = Field(..., ge=0.0, le=1.0, alias="lipRound", description="圆唇程度")
    eye_blink: float = Field(..., ge=0.0, le=1.0, alias="eyeBlink", description="眨眼程度")
    head_pitch: float = Field(..., ge=-1.0, le=1.0, alias="headPitch", description="头部俯仰")
    head_yaw: float = Field(..., ge=-1.0, le=1.0, alias="headYaw", description="头部左右转动")
    gesture: Literal["idle", "beat", "emphasis", "pause"] = Field(..., description="上层动作语义")


class AudioDriveGenerateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    courseware_id: str = Field(..., alias="coursewareId", description="课件唯一标识")
    page_index: int | None = Field(default=None, alias="pageIndex", description="页码")
    audio: AudioMetadata = Field(..., description="音频元信息")
    tokens: list[TokenTimelineItem] = Field(..., description="文本词元时间轴")
    phonemes: list[PhonemeSegment] = Field(..., description="音素/口型片段")
    frames: list[ActionFrame] = Field(..., description="数字人动作驱动帧")
    protocol_json: dict[str, Any] | None = Field(default=None, alias="protocolJson", description="JSON 驱动协议")
    protocol_xml: str | None = Field(default=None, alias="protocolXml", description="XML 驱动协议")
    warnings: list[str] = Field(default_factory=list, description="降级或兼容提示")


class DigitalHumanTaskCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    courseware_id: str | None = Field(default=None, alias="coursewareId")
    page_index: int | None = Field(
        default=None,
        ge=1,
        alias="pageIndex",
        validation_alias=AliasChoices("page_index", "pageIndex", "pageNo"),
    )
    script_text: str | None = Field(default=None, alias="scriptText")
    audio_path: str | None = Field(default=None, alias="audioPath")
    audio_url: str | None = Field(default=None, alias="audioUrl")
    audio_duration_ms: int | None = Field(default=None, gt=0, alias="audioDurationMs")
    frame_interval_ms: int = Field(default=40, ge=20, le=200, alias="frameIntervalMs")
    avatar_id: str = Field(default="default-avatar", alias="avatarId")
    sdk_version: str = Field(default="vendor-neutral-v1", alias="sdkVersion")


class DigitalHumanTaskResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: str = Field(..., alias="taskId")
    status: Literal["PENDING", "RUNNING", "SUCCESS", "FAILED"]
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    phonemes: list[dict[str, Any]] = Field(default_factory=list)
    action_frames: list[dict[str, Any]] = Field(default_factory=list, alias="actionFrames")
    mock_video_required: bool = Field(True, alias="mockVideoRequired")
    message: str | None = None
