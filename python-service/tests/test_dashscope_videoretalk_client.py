from __future__ import annotations

from pathlib import Path

import pytest

from app.clients.dashscope_videoretalk_client import (
    _normalize_optional_policy_value,
    _upload_dashscope_temp_file,
)
from app.core.exceptions import PythonServiceException


def test_normalize_optional_policy_value_handles_bool_and_empty() -> None:
    assert _normalize_optional_policy_value(True) == "true"
    assert _normalize_optional_policy_value(False) == "false"
    assert _normalize_optional_policy_value("private") == "private"
    assert _normalize_optional_policy_value("") is None
    assert _normalize_optional_policy_value(None) is None


def test_upload_dashscope_temp_file_uses_requests_multipart_fields_in_expected_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "avatar.mp4"
    file_path.write_bytes(b"fake-video")
    captured: dict[str, object] = {}

    class DummyResponse:
        status_code = 200
        text = ""

    def fake_post(url: str, *, files: object, timeout: int) -> DummyResponse:
        assert isinstance(files, list)
        field_names = [field_name for field_name, _ in files]
        captured["url"] = url
        captured["field_names"] = field_names
        captured["timeout"] = timeout
        return DummyResponse()

    monkeypatch.setattr("app.clients.dashscope_videoretalk_client.requests.post", fake_post)

    _upload_dashscope_temp_file(
        upload_host="https://example.com/upload",
        file_path=file_path,
        object_key="tmp/avatar.mp4",
        content_type="video/mp4",
        access_key_id="key-id",
        policy="policy-value",
        signature="signature-value",
        object_acl="private",
        forbid_overwrite="true",
        timeout_seconds=180,
    )

    assert captured["url"] == "https://example.com/upload"
    assert captured["timeout"] == 180
    assert captured["field_names"] == [
        "OSSAccessKeyId",
        "Signature",
        "policy",
        "x-oss-object-acl",
        "x-oss-forbid-overwrite",
        "key",
        "success_action_status",
        "file",
    ]


def test_upload_dashscope_temp_file_raises_on_error_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_path = tmp_path / "clip.mp3"
    file_path.write_bytes(b"fake-audio")

    class DummyResponse:
        status_code = 400
        text = "bad multipart"

    def fake_post(url: str, *, files: object, timeout: int) -> DummyResponse:
        return DummyResponse()

    monkeypatch.setattr("app.clients.dashscope_videoretalk_client.requests.post", fake_post)

    with pytest.raises(PythonServiceException, match="DashScope temporary upload failed with status 400"):
        _upload_dashscope_temp_file(
            upload_host="https://example.com/upload",
            file_path=file_path,
            object_key="tmp/clip.mp3",
            content_type="audio/mpeg",
            access_key_id="key-id",
            policy="policy-value",
            signature="signature-value",
            object_acl=None,
            forbid_overwrite=None,
            timeout_seconds=60,
        )
