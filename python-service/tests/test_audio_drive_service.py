from __future__ import annotations

import math
import wave
from pathlib import Path

import pytest

from app.schemas.digital_human import AudioDriveGenerateRequest, AudioDriveGenerateResponse
from app.services.audio_drive_service import generate_audio_drive_protocol


def _write_test_wav(path: Path, *, duration_ms: int = 640, sample_rate: int = 16000) -> None:
    frame_count = int(sample_rate * duration_ms / 1000)
    amplitude = 12000
    frequency = 440
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = bytearray()
        for index in range(frame_count):
            value = int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
            frames.extend(value.to_bytes(2, byteorder="little", signed=True))
        wav_file.writeframes(bytes(frames))


def test_generate_audio_drive_protocol_from_wav(tmp_path: Path):
    audio_path = tmp_path / "tts.wav"
    _write_test_wav(audio_path, duration_ms=640)

    request = AudioDriveGenerateRequest(
        coursewareId="cware_drive_1",
        pageIndex=2,
        scriptText="同学们好，现在我们学习递归定义。",
        audioPath=str(audio_path),
        audioUrl="http://minio.local/tts.wav",
        frameIntervalMs=40,
        protocolFormat="json",
        avatarId="teacher-a",
        sdkVersion="test-v1",
    )

    result = generate_audio_drive_protocol(request)

    assert isinstance(result, AudioDriveGenerateResponse)
    assert result.courseware_id == "cware_drive_1"
    assert result.page_index == 2
    assert result.audio.source == "wav"
    assert 620 <= result.audio.duration_ms <= 660
    assert result.audio.sample_rate == 16000
    assert result.audio.channels == 1
    assert result.tokens
    assert result.phonemes
    assert result.frames
    assert result.frames[0].time_ms == 0
    assert result.protocol_json is not None
    assert result.protocol_json["avatarId"] == "teacher-a"
    assert result.protocol_json["audio"]["url"] == "http://minio.local/tts.wav"
    assert result.protocol_xml is None


def test_generate_audio_drive_protocol_duration_only_with_xml():
    request = AudioDriveGenerateRequest(
        coursewareId="cware_drive_2",
        scriptText="第一步，先理解概念；第二步，再看例子。",
        audioDurationMs=1200,
        protocolFormat="both",
    )

    result = generate_audio_drive_protocol(request)

    assert result.audio.source == "duration-only"
    assert result.audio.duration_ms == 1200
    assert result.protocol_json is not None
    assert result.protocol_xml is not None
    assert result.protocol_xml.startswith("<DigitalHumanDrive")
    assert result.warnings
    assert any(item.token == "，" for item in result.tokens)
    assert all(0.0 <= frame.mouth_open <= 1.0 for frame in result.frames)


def test_audio_drive_request_requires_audio_path_or_duration():
    with pytest.raises(ValueError, match="audioPath"):
        AudioDriveGenerateRequest(
            coursewareId="cware_drive_bad",
            scriptText="没有音频来源。",
        )


def test_generate_audio_drive_endpoint_returns_base_response(request_app, tmp_path: Path):
    audio_path = tmp_path / "tts.wav"
    _write_test_wav(audio_path, duration_ms=480)

    response = request_app(
        "POST",
        "/python/v1/digital-human/audio-drive",
        json={
            "coursewareId": "cware_drive_api",
            "pageIndex": 1,
            "scriptText": "这一页介绍系统目标。",
            "audioPath": str(audio_path),
            "frameIntervalMs": 80,
            "protocolFormat": "xml",
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["code"] == 0
    assert payload["message"] == "success"
    assert payload["data"]["coursewareId"] == "cware_drive_api"
    assert payload["data"]["protocolJson"] is None
    assert payload["data"]["protocolXml"].startswith("<DigitalHumanDrive")
    assert payload["data"]["frames"]
