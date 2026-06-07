from __future__ import annotations

import uuid

from app.core.exceptions import AppException, BUSINESS_VALIDATION_FAILED
from app.schemas.digital_human import (
    AudioDriveGenerateRequest,
    DigitalHumanTaskCreateRequest,
    DigitalHumanTaskResponse,
)
from app.services.audio_drive_service import generate_audio_drive_protocol
from app.utils.logger import logger

_TASKS: dict[str, DigitalHumanTaskResponse] = {}


def create_digital_human_task(request: DigitalHumanTaskCreateRequest) -> dict[str, object]:
    task_id = f"py_dh_{uuid.uuid4().hex[:12]}"

    try:
        if _can_generate_audio_drive(request):
            drive = generate_audio_drive_protocol(_to_audio_drive_request(request))
            task = DigitalHumanTaskResponse(
                taskId=task_id,
                status="SUCCESS",
                timeline=[item.model_dump(by_alias=True) for item in drive.tokens],
                phonemes=[item.model_dump(by_alias=True) for item in drive.phonemes],
                actionFrames=[item.model_dump(by_alias=True) for item in drive.frames],
                mockVideoRequired=True,
                message="Audio drive protocol generated; mock video rendering is still required.",
            )
        else:
            task = DigitalHumanTaskResponse(
                taskId=task_id,
                status="SUCCESS",
                timeline=[],
                phonemes=[],
                actionFrames=[],
                mockVideoRequired=True,
                message="No audio source provided; returned minimal mock digital-human task protocol.",
            )
        _TASKS[task_id] = task
        logger.info("Digital-human task completed. taskId=%s status=%s", task_id, task.status)
        return task.model_dump(by_alias=True)
    except Exception as exc:  # noqa: BLE001
        task = DigitalHumanTaskResponse(
            taskId=task_id,
            status="FAILED",
            timeline=[],
            phonemes=[],
            actionFrames=[],
            mockVideoRequired=True,
            message=str(exc),
        )
        _TASKS[task_id] = task
        logger.warning("Digital-human task failed. taskId=%s reason=%s", task_id, str(exc))
        return task.model_dump(by_alias=True)


def get_digital_human_task(task_id: str) -> dict[str, object]:
    task = _TASKS.get(task_id)
    if task is None:
        raise AppException(BUSINESS_VALIDATION_FAILED, "Digital-human task not found")
    return task.model_dump(by_alias=True)


def _can_generate_audio_drive(request: DigitalHumanTaskCreateRequest) -> bool:
    return bool(request.script_text and (request.audio_path or request.audio_duration_ms))


def _to_audio_drive_request(request: DigitalHumanTaskCreateRequest) -> AudioDriveGenerateRequest:
    return AudioDriveGenerateRequest(
        coursewareId=request.courseware_id or "unknown_courseware",
        pageIndex=request.page_index,
        scriptText=request.script_text or "数字人讲解文本暂未提供。",
        audioPath=request.audio_path,
        audioUrl=request.audio_url,
        audioDurationMs=request.audio_duration_ms,
        frameIntervalMs=request.frame_interval_ms,
        protocolFormat="json",
        avatarId=request.avatar_id,
        sdkVersion=request.sdk_version,
    )


def clear_digital_human_tasks_for_test() -> None:
    _TASKS.clear()
