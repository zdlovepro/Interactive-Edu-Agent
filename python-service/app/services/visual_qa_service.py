from __future__ import annotations

import time
from dataclasses import dataclass

from app.clients.llm_client import get_llm_client
from app.clients.vision_client import get_vision_client
from app.core.config import settings
from app.schemas.qa import QaAskTextRequest
from app.schemas.rag import RagAskRequest, RagVisualAskRequest
from app.services.rag_service import answer_question
from app.utils.logger import logger

try:  # pragma: no cover - real LangChain messages are used when installed
    from langchain.schema import HumanMessage, SystemMessage
except Exception:  # noqa: BLE001  # pragma: no cover
    @dataclass
    class _FallbackMessage:
        content: str
        type: str

    class SystemMessage(_FallbackMessage):
        def __init__(self, content: str) -> None:
            super().__init__(content=content, type="system")

    class HumanMessage(_FallbackMessage):
        def __init__(self, content: str) -> None:
            super().__init__(content=content, type="human")


_FALLBACK_VISION_DISABLED = "vision_model_disabled"
_FALLBACK_IMAGE_MISSING = "page_image_missing"
_FALLBACK_VISION_ERROR = "vision_model_error"


def answer_rag_question(request: RagAskRequest) -> dict[str, object]:
    qa_request = QaAskTextRequest(
        sessionId=request.session_id,
        coursewareId=request.courseware_id,
        pageIndex=request.page_index,
        question=request.question,
        topK=request.top_k,
    )
    return answer_question(qa_request).model_dump(by_alias=True)


def answer_visual_question(request: RagVisualAskRequest) -> dict[str, object]:
    start_at = time.perf_counter()
    evidence = _build_visual_evidence(request)
    image_ref = _select_image_reference(request)
    fallback_reason = _FALLBACK_VISION_DISABLED

    if _vision_enabled():
        if image_ref:
            try:
                client = get_vision_client()
                answer = client.ask_page(
                    page_no=request.page_no,
                    image=image_ref,
                    question=request.question,
                    page_text=request.page_text,
                    visual_summary=request.visual_summary,
                )
                if answer.strip():
                    return _build_visual_response(
                        answer,
                        evidence,
                        start_at,
                        used_vision=True,
                        fallback_used=False,
                        fallback_reason=None,
                        vision_provider=client.provider,
                        model=client.model,
                    )
            except Exception as exc:  # noqa: BLE001
                fallback_reason = _FALLBACK_VISION_ERROR
                logger.warning(
                    "Vision QA degraded to text fallback. coursewareId=%s pageNo=%s reason=%s",
                    request.courseware_id,
                    request.page_no,
                    str(exc),
                )
        else:
            fallback_reason = _FALLBACK_IMAGE_MISSING

    text_answer = _answer_with_text_context(request, evidence)
    return _build_visual_response(
        text_answer,
        evidence,
        start_at,
        used_vision=False,
        fallback_used=True,
        fallback_reason=fallback_reason,
        vision_provider=settings.VISION_PROVIDER if settings.VISION_PROVIDER else None,
        model=settings.VISION_MODEL_NAME if settings.VISION_MODEL_NAME else None,
    )


def _answer_with_text_context(request: RagVisualAskRequest, evidence: list[dict[str, object]]) -> str:
    if settings.LLM_API_KEY and evidence:
        try:
            answer = get_llm_client().invoke(_build_visual_messages(request, evidence)).strip()
            if answer:
                return answer
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Visual QA text fallback degraded to template answer. coursewareId=%s pageNo=%s reason=%s",
                request.courseware_id,
                request.page_no,
                str(exc),
            )
    return _build_template_visual_answer(request)


def _build_visual_messages(request: RagVisualAskRequest, evidence: list[dict[str, object]]) -> list[SystemMessage | HumanMessage]:
    return [
        SystemMessage(
            content=(
                "You are a classroom visual QA assistant. Answer in Simplified Chinese. "
                "Use only the given page text, visual summary, and page image reference."
            )
        ),
        HumanMessage(content=_build_visual_prompt(request, evidence)),
    ]


def _build_visual_prompt(request: RagVisualAskRequest, evidence: list[dict[str, object]]) -> str:
    lines = [
        f"Courseware ID: {request.courseware_id}",
        f"Page number: {request.page_no}",
        f"Question: {request.question.strip()}",
        "Evidence:",
    ]
    for item in evidence:
        lines.append(f"- {item['type']}: {item['content']}")
    lines.append("Please answer concisely in Chinese.")
    return "\n".join(lines)


def _build_visual_evidence(request: RagVisualAskRequest) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    if request.visual_summary.strip():
        evidence.append(
            {
                "pageNo": request.page_no,
                "type": "visualSummary",
                "content": request.visual_summary.strip(),
            }
        )
    if request.page_text.strip():
        evidence.append(
            {
                "pageNo": request.page_no,
                "type": "pageText",
                "content": _trim(request.page_text, limit=500),
            }
        )
    if request.page_image_path:
        evidence.append(
            {
                "pageNo": request.page_no,
                "type": "pageImagePath",
                "content": request.page_image_path,
            }
        )
    if request.page_image_url:
        evidence.append(
            {
                "pageNo": request.page_no,
                "type": "pageImageUrl",
                "content": request.page_image_url,
            }
        )
    return evidence


def _select_image_reference(request: RagVisualAskRequest) -> str | None:
    if request.page_image_path and request.page_image_path.strip():
        return request.page_image_path.strip()
    if request.page_image_url and request.page_image_url.strip():
        return request.page_image_url.strip()
    return None


def _vision_enabled() -> bool:
    return bool(
        settings.VISION_ENABLED
        and settings.VISION_API_KEY
        and settings.VISION_API_BASE
        and settings.VISION_MODEL_NAME
    )


def _build_template_visual_answer(request: RagVisualAskRequest) -> str:
    visual_summary = request.visual_summary.strip()
    page_text = request.page_text.strip()
    if visual_summary and page_text:
        return f"根据第 {request.page_no} 页的视觉摘要和文字内容，这一页主要说明：{_trim(visual_summary)} 相关文字补充为：{_trim(page_text)}"
    if visual_summary:
        return f"根据第 {request.page_no} 页的视觉摘要，这张图主要表示：{_trim(visual_summary)}"
    if page_text:
        return f"第 {request.page_no} 页暂时没有可用视觉模型结果，可以先依据页面文字理解：{_trim(page_text)}"
    return "当前页缺少 pageText 和 visualSummary，暂时无法可靠回答这张图的含义。"


def _build_visual_response(
    answer: str,
    evidence: list[dict[str, object]],
    start_at: float,
    *,
    used_vision: bool,
    fallback_used: bool,
    fallback_reason: str | None,
    vision_provider: str | None,
    model: str | None,
) -> dict[str, object]:
    return {
        "answer": answer.strip(),
        "usedVision": used_vision,
        "fallbackUsed": fallback_used,
        "fallbackReason": fallback_reason,
        "visionProvider": vision_provider,
        "model": model,
        "evidence": evidence,
        "latencyMs": max(1, int((time.perf_counter() - start_at) * 1000)),
    }


def _trim(text: str, limit: int = 220) -> str:
    normalized = " ".join(str(text or "").split()).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."
