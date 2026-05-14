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
        resolved = Path(image_path)
        if not resolved.exists() or not resolved.is_file():
            raise PythonServiceException(f"视觉摘要图片不存在: {resolved}")

        data_url = _image_to_data_url(resolved)
        prompt_hint = (hint_text or "").strip()

        system = (
            "你是课件视觉理解助手。给定一张课件页/幻灯片截图，请输出严格 JSON（不要 Markdown 代码块）。"
            "JSON 格式为：{\"visual_summary\": string, \"objects\": string[]}。"
            "objects 只包含你能明确判断存在的类别，例如：图表、表格、流程图、公式、图片、代码、示意图。"
            "visual_summary 用中文，1-3 句，突出图表/表格的关键信息（如轴含义、趋势、对比项、结论）。"
        )

        user_text = (
            f"页面索引（1-based）: {page_index}\n"
            + (f"该页可提取文本（可能不完整）:\n{prompt_hint}\n" if prompt_hint else "")
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


def _image_to_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    raw = image_path.read_bytes()
    encoded = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _extract_json_object(text: str) -> dict:
    stripped = text.strip()
    # Best-effort strip markdown fences.
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
