from __future__ import annotations

import asyncio
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp
import requests

from app.core.config import settings
from app.core.exceptions import PythonServiceException, THIRD_PARTY_SERVICE_ERROR
from app.utils.logger import logger


@dataclass(frozen=True)
class UploadedResource:
    file_name: str
    resource_url: str


class DashScopeDigitalHumanClient:
    def __init__(self) -> None:
        api_key = (settings.DIGITAL_HUMAN_API_KEY or "").strip()
        if not api_key:
            raise PythonServiceException(
                "Digital human service is not configured with a DashScope API key",
                code=THIRD_PARTY_SERVICE_ERROR,
            )

        self._api_key = api_key
        self._base_url = settings.DIGITAL_HUMAN_API_BASE.rstrip("/")
        self._model_name = (settings.DIGITAL_HUMAN_MODEL_NAME or "wan2.7-r2v").strip()
        self._timeout = aiohttp.ClientTimeout(total=max(60, settings.DIGITAL_HUMAN_TASK_TIMEOUT_SECONDS + 60))
        self._session: aiohttp.ClientSession | None = None
        self._reference_image_upload: UploadedResource | None = None

    async def __aenter__(self) -> "DashScopeDigitalHumanClient":
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def render_clip(
        self,
        *,
        reference_image_path: Path,
        reference_voice_path: Path | None,
        prompt: str,
        output_path: Path,
        duration_seconds: int,
    ) -> Path:
        session = self._require_session()
        image_resource = await self._ensure_reference_image_uploaded(session, reference_image_path)
        voice_resource = (
            await self._upload_file(session, reference_voice_path)
            if reference_voice_path is not None
            else None
        )

        task_id = await self._submit_task(
            session,
            prompt=prompt,
            reference_image_url=image_resource.resource_url,
            reference_voice_url=voice_resource.resource_url if voice_resource else None,
            duration_seconds=duration_seconds,
        )
        result_url = await self._wait_for_task_result(session, task_id)
        await self._download_file(session, result_url, output_path)
        return output_path

    def _require_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("DashScopeDigitalHumanClient must be used as an async context manager")
        return self._session

    async def _ensure_reference_image_uploaded(
        self,
        session: aiohttp.ClientSession,
        reference_image_path: Path,
    ) -> UploadedResource:
        if self._reference_image_upload is None:
            self._reference_image_upload = await self._upload_file(session, reference_image_path)
        return self._reference_image_upload

    async def _upload_file(
        self,
        session: aiohttp.ClientSession,
        file_path: Path,
    ) -> UploadedResource:
        file_path = file_path.expanduser().resolve()
        if not file_path.exists() or not file_path.is_file():
            raise PythonServiceException(f"Digital human source file not found: {file_path}")

        policy_url = f"{self._base_url}/api/v1/uploads?action=getPolicy&model={self._model_name}"
        policy_response = await self._request_json(session, "GET", policy_url)

        data = policy_response.get("data") or {}
        upload_host = str(data.get("upload_host") or "").strip()
        upload_dir = str(data.get("upload_dir") or "").strip().strip("/")
        policy = str(data.get("policy") or "").strip()
        signature = str(data.get("signature") or "").strip()
        access_key_id = str(data.get("oss_access_key_id") or "").strip()

        if not upload_host or not upload_dir or not policy or not signature or not access_key_id:
            raise PythonServiceException("DashScope upload policy response is incomplete")

        object_key = f"{upload_dir}/{file_path.name}"
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        await asyncio.to_thread(
            _upload_dashscope_temp_file,
            upload_host=upload_host,
            file_path=file_path,
            object_key=object_key,
            content_type=content_type,
            access_key_id=access_key_id,
            policy=policy,
            signature=signature,
            object_acl=_normalize_optional_policy_value(data.get("x_oss_object_acl")),
            forbid_overwrite=_normalize_optional_policy_value(data.get("x_oss_forbid_overwrite")),
            timeout_seconds=max(60, settings.DIGITAL_HUMAN_TASK_TIMEOUT_SECONDS),
        )

        resource_url = f"oss://{object_key}"
        logger.info("DashScope temporary file uploaded. file=%s", file_path.name)
        return UploadedResource(file_name=file_path.name, resource_url=resource_url)

    async def _submit_task(
        self,
        session: aiohttp.ClientSession,
        *,
        prompt: str,
        reference_image_url: str,
        reference_voice_url: str | None,
        duration_seconds: int,
    ) -> str:
        task_url = f"{self._base_url}/api/v1/services/aigc/video-generation/video-synthesis"
        media_item: dict[str, Any] = {
            "type": "reference_image",
            "url": reference_image_url,
        }
        if reference_voice_url:
            media_item["reference_voice"] = reference_voice_url

        response = await self._request_json(
            session,
            "POST",
            task_url,
            headers={
                "Content-Type": "application/json",
                "X-DashScope-Async": "enable",
                "X-DashScope-OssResourceResolve": "enable",
            },
            json_body={
                "model": self._model_name,
                "input": {
                    "prompt": prompt,
                    "media": [media_item],
                },
                "parameters": {
                    "resolution": settings.DIGITAL_HUMAN_RESOLUTION,
                    "ratio": settings.DIGITAL_HUMAN_RATIO,
                    "duration": max(2, min(15, duration_seconds)),
                    "prompt_extend": settings.DIGITAL_HUMAN_PROMPT_EXTEND,
                    "watermark": settings.DIGITAL_HUMAN_WATERMARK,
                },
            },
        )

        task_id = (
            response.get("output", {}).get("task_id")
            or response.get("output", {}).get("taskId")
            or response.get("task_id")
            or response.get("taskId")
        )
        if not task_id:
            raise PythonServiceException("DashScope digital human task did not return a task id")

        logger.info("DashScope digital human task submitted. taskId=%s", task_id)
        return str(task_id)

    async def _wait_for_task_result(
        self,
        session: aiohttp.ClientSession,
        task_id: str,
    ) -> str:
        task_url = f"{self._base_url}/api/v1/tasks/{task_id}"
        timeout_seconds = max(60, settings.DIGITAL_HUMAN_TASK_TIMEOUT_SECONDS)
        poll_interval = max(1, settings.DIGITAL_HUMAN_POLL_INTERVAL_SECONDS)
        deadline = asyncio.get_running_loop().time() + timeout_seconds

        while True:
            response = await self._request_json(
                session,
                "GET",
                task_url,
                headers={"X-DashScope-OssResourceResolve": "enable"},
            )

            output = response.get("output") or {}
            task_status = str(
                output.get("task_status")
                or output.get("taskStatus")
                or response.get("task_status")
                or response.get("taskStatus")
                or ""
            ).upper()

            if task_status in {"SUCCEEDED", "SUCCESS"}:
                result_url = _extract_result_video_url(output) or _extract_result_video_url(response)
                if not result_url:
                    raise PythonServiceException("DashScope digital human task succeeded without a downloadable video URL")
                logger.info("DashScope digital human task finished. taskId=%s", task_id)
                return result_url

            if task_status in {"FAILED", "FAIL", "CANCELED", "CANCELLED"}:
                message = _extract_error_message(output) or _extract_error_message(response) or "unknown error"
                raise PythonServiceException(f"DashScope digital human task failed: {message}")

            if asyncio.get_running_loop().time() >= deadline:
                raise PythonServiceException("DashScope digital human task timed out")

            await asyncio.sleep(poll_interval)

    async def _download_file(
        self,
        session: aiohttp.ClientSession,
        url: str,
        output_path: Path,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with session.get(url) as response:
            if response.status >= 400:
                text = await response.text()
                raise PythonServiceException(
                    f"DashScope digital human result download failed with status {response.status}: {text[:200]}"
                )
            output_path.write_bytes(await response.read())

        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise PythonServiceException("DashScope digital human result is empty")

    async def _request_json(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        async with session.request(method, url, headers=request_headers, json=json_body) as response:
            text = await response.text()
            if response.status >= 400:
                raise PythonServiceException(
                    f"DashScope request failed with status {response.status}: {text[:200]}",
                    code=THIRD_PARTY_SERVICE_ERROR,
                )

        try:
            data = json.loads(text or "{}")
        except json.JSONDecodeError as exc:
            raise PythonServiceException("DashScope returned a non-JSON response") from exc
        if not isinstance(data, dict):
            raise PythonServiceException("DashScope returned an invalid JSON envelope")
        return data


def _extract_result_video_url(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("video_url", "videoUrl", "url"):
            value = payload.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        for value in payload.values():
            result = _extract_result_video_url(value)
            if result:
                return result
    elif isinstance(payload, list):
        for item in payload:
            result = _extract_result_video_url(item)
            if result:
                return result
    return None


def _extract_error_message(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("message", "msg", "error_message", "errorMessage"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in payload.values():
            result = _extract_error_message(value)
            if result:
                return result
    elif isinstance(payload, list):
        for item in payload:
            result = _extract_error_message(item)
            if result:
                return result
    return None


def _normalize_optional_policy_value(raw_value: Any) -> str | None:
    if raw_value in (None, ""):
        return None
    if isinstance(raw_value, bool):
        return str(raw_value).lower()
    return str(raw_value)


def _upload_dashscope_temp_file(
    *,
    upload_host: str,
    file_path: Path,
    object_key: str,
    content_type: str,
    access_key_id: str,
    policy: str,
    signature: str,
    object_acl: str | None,
    forbid_overwrite: str | None,
    timeout_seconds: int,
) -> None:
    multipart_fields: list[tuple[str, tuple[None, str] | tuple[str, Any, str]]] = [
        ("OSSAccessKeyId", (None, access_key_id)),
        ("Signature", (None, signature)),
        ("policy", (None, policy)),
    ]
    if object_acl:
        multipart_fields.append(("x-oss-object-acl", (None, object_acl)))
    if forbid_overwrite:
        multipart_fields.append(("x-oss-forbid-overwrite", (None, forbid_overwrite)))
    multipart_fields.extend(
        [
            ("key", (None, object_key)),
            ("success_action_status", (None, "200")),
        ]
    )

    with file_path.open("rb") as file_handle:
        multipart_fields.append(("file", (file_path.name, file_handle, content_type)))
        response = requests.post(upload_host, files=multipart_fields, timeout=timeout_seconds)

    if response.status_code >= 400:
        raise PythonServiceException(
            f"DashScope temporary upload failed with status {response.status_code}: {response.text[:200]}"
        )


DashScopeVideoRetalkClient = DashScopeDigitalHumanClient
