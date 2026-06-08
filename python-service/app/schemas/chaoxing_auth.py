from __future__ import annotations

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class _ConfiguredModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class ChaoxingAuthSessionCreateRequest(_ConfiguredModel):
    course_url: str | None = Field(None, validation_alias=AliasChoices("course_url", "courseUrl"))
    user_agent: str | None = Field(None, validation_alias=AliasChoices("user_agent", "userAgent"))


class ChaoxingAuthSessionView(_ConfiguredModel):
    session_id: str = Field(..., serialization_alias="sessionId")
    status: str
    qr_code_url: str | None = Field(None, serialization_alias="qrCodeUrl")
    message: str | None = None
    expires_at: str | None = Field(None, serialization_alias="expiresAt")
    authorized_at: str | None = Field(None, serialization_alias="authorizedAt")
