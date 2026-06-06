from __future__ import annotations

import time
from dataclasses import dataclass

from app.clients.llm_client import get_llm_client
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

_VISUAL_FALLBACK_REASON = "未配置真实多模态视觉问答模型，已使用 pageText 和 visualSummary 生成回答。"


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

    if settings.LLM_API_KEY and evidence:
        try:
            answer = get_llm_client().invoke(_build_visual_messages(request, evidence)).strip()
            if answer:
                return _build_visual_response(answer, evidence, start_at)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Visual QA degraded to template answer. coursewareId=%s pageNo=%s reason=%s",
                request.courseware_id,
                request.page_no,
                str(exc),
            )

    return _build_visual_response(_build_template_visual_answer(request), evidence, start_at)


def _build_visual_messages(request: RagVisualAskRequest, evidence: list[dict[str, object]]) -> list[SystemMessage | HumanMessage]:
    return [
        SystemMessage(content="你是课堂视觉问答助手。只能依据给定页面文本和视觉摘要回答，不要补充课件之外的信息。"),
        HumanMessage(content=_build_visual_prompt(request, evidence)),
    ]


def _build_visual_prompt(request: RagVisualAskRequest, evidence: list[dict[str, object]]) -> str:
    lines = [
        f"课件ID：{request.courseware_id}",
        f"页码：{request.page_no}",
        f"问题：{request.question.strip()}",
        "证据：",
    ]
    for item in evidence:
        lines.append(f"- {item['type']}: {item['content']}")
    lines.append("请用中文简洁回答。")
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
    if request.page_image_url:
        evidence.append(
            {
                "pageNo": request.page_no,
                "type": "pageImageUrl",
                "content": request.page_image_url,
            }
        )
    return evidence


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


def _build_visual_response(answer: str, evidence: list[dict[str, object]], start_at: float) -> dict[str, object]:
    return {
        "answer": answer.strip(),
        "usedVision": False,
        "fallbackReason": _VISUAL_FALLBACK_REASON,
        "evidence": evidence,
        "latencyMs": max(1, int((time.perf_counter() - start_at) * 1000)),
    }


def _trim(text: str, limit: int = 220) -> str:
    normalized = " ".join(str(text or "").split()).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."
