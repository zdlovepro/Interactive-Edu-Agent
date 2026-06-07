from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any

try:  # pragma: no cover - real OpenAI client is used when installed
    import httpx
    from openai import OpenAI
except ImportError:  # pragma: no cover - keeps fallback endpoints importable in slim envs
    httpx = None
    OpenAI = None

from app.core.config import settings
from app.core.exceptions import ModelOutputException, PythonServiceException, THIRD_PARTY_SERVICE_ERROR
from app.schemas.visual import VisualSummary
from app.utils.logger import logger


class VisionClient:
    """OpenAI-compatible vision client for Qwen VL via Alibaba Cloud Bailian."""

    def __init__(self) -> None:
        if not settings.VISION_ENABLED:
            raise PythonServiceException("Vision model is disabled", code=THIRD_PARTY_SERVICE_ERROR)
        if not settings.VISION_API_KEY:
            raise PythonServiceException("VISION_API_KEY or DASHSCOPE_API_KEY is missing", code=THIRD_PARTY_SERVICE_ERROR)
        if not settings.VISION_API_BASE:
            raise PythonServiceException("VISION_API_BASE is missing", code=THIRD_PARTY_SERVICE_ERROR)
        if not settings.VISION_MODEL_NAME:
            raise PythonServiceException("VISION_MODEL_NAME is missing", code=THIRD_PARTY_SERVICE_ERROR)
        if OpenAI is None:
            raise PythonServiceException("Vision API dependency openai is not installed", code=THIRD_PARTY_SERVICE_ERROR)
        if httpx is None:
            raise PythonServiceException("Vision API dependency httpx is not installed", code=THIRD_PARTY_SERVICE_ERROR)

        self._client = OpenAI(
            api_key=settings.VISION_API_KEY,
            base_url=settings.VISION_API_BASE,
            http_client=httpx.Client(trust_env=settings.VISION_TRUST_ENV_PROXY),
        )

    @property
    def provider(self) -> str:
        return settings.VISION_PROVIDER

    @property
    def model(self) -> str:
        return settings.VISION_MODEL_NAME

    def summarize_page(self, page_index: int, image_path: str | Path, hint_text: str | None = None) -> VisualSummary:
        image_url = _image_to_openai_url(image_path)
        prompt_hint = (hint_text or "").strip()

        system = (
            "You are a courseware visual understanding assistant. "
            "Return strict JSON only, without markdown fences. "
            'Schema: {"visual_summary": string, "objects": string[]}. '
            "Write visual_summary in Simplified Chinese, 1 to 3 sentences."
        )
        user_text = (
            f"Page index is 1-based: {page_index}\n"
            + (f"Extracted page text, possibly incomplete:\n{prompt_hint}\n" if prompt_hint else "")
            + "Summarize charts, tables, formulas, diagrams, images, and important visual relations."
        )

        logger.info(
            "Invoking vision model for visual summary. pageIndex=%s provider=%s model=%s",
            page_index,
            settings.VISION_PROVIDER,
            settings.VISION_MODEL_NAME,
        )

        content = self._invoke(
            [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ]
        )

        payload = _extract_json_object(content)
        try:
            visual_summary = VisualSummary(
                page_index=page_index,
                visual_summary=str(payload.get("visual_summary") or "").strip(),
                objects=[item for item in (payload.get("objects") or []) if isinstance(item, str) and item.strip()],
            )
        except Exception as exc:  # noqa: BLE001
            raise ModelOutputException(f"Vision summary structure validation failed: {exc}") from exc

        if not visual_summary.visual_summary.strip():
            raise ModelOutputException("Vision summary is empty")

        return visual_summary

    def ask_page(
        self,
        *,
        page_no: int,
        image: str | Path,
        question: str,
        page_text: str = "",
        visual_summary: str = "",
    ) -> str:
        image_url = _image_to_openai_url(image)
        context_lines = [
            f"Page number: {page_no}",
            f"Question: {question.strip()}",
        ]
        if page_text.strip():
            context_lines.append(f"Extracted page text:\n{page_text.strip()}")
        if visual_summary.strip():
            context_lines.append(f"Existing visual summary:\n{visual_summary.strip()}")

        prompt = (
            "\n\n".join(context_lines)
            + "\n\nAnswer in Simplified Chinese. Use the image as primary evidence, "
            "and use page text or visual summary only as supplemental context. "
            "If the image is insufficient, say so briefly and then answer from the provided text."
        )

        logger.info(
            "Invoking vision model for visual QA. pageNo=%s provider=%s model=%s",
            page_no,
            settings.VISION_PROVIDER,
            settings.VISION_MODEL_NAME,
        )

        return self._invoke(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ]
        )

    def _invoke(self, messages: list[dict[str, Any]]) -> str:
        response = self._client.chat.completions.create(
            model=settings.VISION_MODEL_NAME,
            messages=messages,
            temperature=settings.VISION_TEMPERATURE,
            max_tokens=settings.VISION_MAX_TOKENS,
            timeout=settings.VISION_TIMEOUT,
        )
        content = response.choices[0].message.content if response.choices else None
        if not content or not content.strip():
            raise ModelOutputException("Vision model returned empty content")
        return content.strip()


def _image_to_openai_url(image: str | Path) -> str:
    raw = str(image or "").strip()
    if not raw:
        raise PythonServiceException("Vision image is empty", code=THIRD_PARTY_SERVICE_ERROR)
    if raw.startswith(("http://", "https://", "data:")):
        return raw

    path = Path(raw).expanduser()
    if not path.exists() or not path.is_file():
        raise PythonServiceException(f"Vision image file not found: {path}", code=THIRD_PARTY_SERVICE_ERROR)

    size = path.stat().st_size
    if size > settings.VISION_MAX_IMAGE_BYTES:
        raise PythonServiceException(
            "Vision image is too large for base64 input; use a public URL or compressed image",
            code=THIRD_PARTY_SERVICE_ERROR,
        )

    mime_type, _ = mimetypes.guess_type(str(path))
    mime_type = mime_type or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", stripped)
        stripped = re.sub(r"\n```$", "", stripped)
        stripped = stripped.strip()

    match = _JSON_RE.search(stripped)
    candidate = match.group(0) if match else stripped

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ModelOutputException(f"Vision model output is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ModelOutputException("Vision model JSON output is not an object")

    return data


_vision_client: VisionClient | None = None


def get_vision_client() -> VisionClient:
    global _vision_client
    if _vision_client is None:
        _vision_client = VisionClient()
    return _vision_client


def clear_vision_client_for_test() -> None:
    global _vision_client
    _vision_client = None
