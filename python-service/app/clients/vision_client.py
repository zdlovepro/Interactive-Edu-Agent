from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from openai import OpenAI

from app.core.config import settings
from app.core.exceptions import ModelOutputException, PythonServiceException, THIRD_PARTY_SERVICE_ERROR
from app.schemas.visual import VisualSummary
from app.utils.logger import logger


class VisionClient:
    def __init__(self) -> None:
        if not settings.VISION_API_KEY:
            raise PythonServiceException("VISION 服务未配置", code=THIRD_PARTY_SERVICE_ERROR)
        if not settings.VISION_API_BASE:
            raise PythonServiceException("VISION_API_BASE 未配置", code=THIRD_PARTY_SERVICE_ERROR)
        if not settings.VISION_MODEL_NAME:
            raise PythonServiceException("VISION_MODEL_NAME 未配置", code=THIRD_PARTY_SERVICE_ERROR)

        self._client = OpenAI(
            api_key=settings.VISION_API_KEY,
            base_url=settings.VISION_API_BASE,
        )

    def summarize_page(self, page_index: int, image_path: str | Path, hint_text: str | None = None) -> VisualSummary:
        resolved = _resolve_existing_image(image_path)
        data_url = _image_to_data_url(resolved)
        prompt_hint = (hint_text or "").strip()

        system = (
            "你是课件视觉理解助手。给定一张课件页截图，请只输出严格 JSON，"
            "格式为 {\"visual_summary\": string, \"objects\": string[]}。"
            "visual_summary 用中文 1-3 句总结页面图示/表格/公式要点；"
            "objects 只保留明确可见的对象类别。"
        )
        user_text = (
            f"页面索引（1-based）：{page_index}\n"
            + (f"该页已知文本提示：\n{prompt_hint}\n" if prompt_hint else "")
            + "请仅返回 JSON。"
        )

        logger.info(
            "Invoking vision model for visual summary. pageIndex=%s model=%s image=%s",
            page_index,
            settings.VISION_MODEL_NAME,
            resolved.name,
        )

        response = self._client.chat.completions.create(
            model=settings.VISION_MODEL_NAME,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            temperature=settings.VISION_TEMPERATURE,
            max_tokens=settings.VISION_MAX_TOKENS,
            timeout=settings.VISION_TIMEOUT,
        )

        content = response.choices[0].message.content if response.choices else None
        if not content or not content.strip():
            raise ModelOutputException("视觉模型未返回有效内容")

        payload = _extract_json_object(content)
        try:
            visual_summary = VisualSummary(
                page_index=page_index,
                visual_summary=str(payload.get("visual_summary") or "").strip(),
                objects=[item for item in (payload.get("objects") or []) if isinstance(item, str) and item.strip()],
            )
        except Exception as exc:  # noqa: BLE001
            raise ModelOutputException(f"视觉摘要结构校验失败: {exc}") from exc

        if not visual_summary.visual_summary.strip():
            raise ModelOutputException("视觉摘要为空")

        return visual_summary

    def answer_page_question(
        self,
        *,
        page_index: int,
        question: str,
        image_path: str | Path,
        hint_text: str | None = None,
    ) -> str:
        resolved = _resolve_existing_image(image_path)
        data_url = _image_to_data_url(resolved)
        prompt_hint = (hint_text or "").strip()

        system = (
            "你是课件答疑助手。你的任务是根据单张课件截图回答问题。"
            "回答必须严格依据图片中能看到的内容，以及用户提供的同页文字提示；"
            "不允许补充课件外的背景知识。"
            "如果图片里无法确认答案，请明确回答“课件中没有直接覆盖该内容”。"
            "回答使用中文，简洁自然，适合课堂答疑。"
        )
        user_text = (
            f"页面索引（1-based）：{page_index}\n"
            f"学生问题：{question.strip()}\n"
            + (f"同页文字提示：\n{prompt_hint}\n" if prompt_hint else "")
            + "请只依据当前这张图回答。"
        )

        logger.info(
            "Invoking vision model for page QA. pageIndex=%s model=%s image=%s",
            page_index,
            settings.VISION_MODEL_NAME,
            resolved.name,
        )

        response = self._client.chat.completions.create(
            model=settings.VISION_MODEL_NAME,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            temperature=min(settings.VISION_TEMPERATURE, 0.3),
            max_tokens=max(settings.VISION_MAX_TOKENS, 256),
            timeout=settings.VISION_TIMEOUT,
        )

        content = response.choices[0].message.content if response.choices else None
        if not content or not content.strip():
            raise ModelOutputException("视觉问答未返回有效内容")
        return str(content).strip()


def _resolve_existing_image(image_path: str | Path) -> Path:
    resolved = Path(image_path)
    if not resolved.exists() or not resolved.is_file():
        raise PythonServiceException(f"视觉输入图片不存在: {resolved}")
    return resolved


def _image_to_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    raw = image_path.read_bytes()
    encoded = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


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
        raise ModelOutputException(f"视觉模型输出不是合法 JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ModelOutputException("视觉模型输出 JSON 不是对象")
    return data


_vision_client: VisionClient | None = None


def get_vision_client() -> VisionClient:
    global _vision_client
    if _vision_client is None:
        _vision_client = VisionClient()
    return _vision_client
