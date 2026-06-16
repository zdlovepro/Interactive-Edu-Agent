from __future__ import annotations

import math
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass

try:  # pragma: no cover - real LangChain messages are used when installed
    from langchain.schema import HumanMessage, SystemMessage
except ImportError:  # pragma: no cover - keeps QA fallback importable without LangChain
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

from app.clients.llm_client import get_llm_client
from app.clients.vision_client import get_vision_client
from app.core.config import settings
from app.schemas.qa import QaAskTextRequest, QaAskTextResponse, QaEvidenceItem
from app.services.rag_retriever import retrieve_context
from app.utils.logger import logger

_SYSTEM_PROMPT = """\
你是课堂中的 AI 助教。回答范围是整份课件，当前页码只表示学生此刻看到的位置，不能把回答限制在当前页。
请优先依据提供的课件证据作答，可以综合多个页面的信息给出简洁、自然的解释。
只有当整份课件的证据都不足以支持回答时，才明确回答“课件中没有直接覆盖该内容”。
不要编造课件之外的事实，也不要输出与问题无关的扩展内容。
"""

_GENERAL_FALLBACK_SYSTEM_PROMPT = """\
你是课堂中的 AI 助教。当检索不到足够的课件证据时，允许你基于通用知识回答学生问题。
如果回答使用了通用知识，请在开头简短说明“下面给出通用解释：”。
如果已经提供了整份课件中相关页面的概览，请优先参考这些线索，使回答尽量贴合本课程。
回答保持简洁、自然，不要输出与问题无关的扩展内容。
"""

_NO_EVIDENCE_ANSWER = "课件中没有直接覆盖该内容。你可以换个更贴近当前课程主题的问题，或者告诉我你想确认哪个概念。"
_STREAM_FALLBACK_CHUNK_SIZE = 12
_COURSEWARE_HINT_LIMIT = 4
_CURRENT_PAGE_TEXT_SCORE = 0.72
_CURRENT_PAGE_VISUAL_SCORE = 0.54
_VISUAL_QUESTION_PATTERN = re.compile(r"(图表|图片|截图|流程图|示意图|曲线|柱状图|饼图|公式|界面|这张图|这一页图里)")
_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+")
_DEFINITION_PATTERNS = (
    re.compile(r"^\s*什么是(?P<term>.+)$"),
    re.compile(r"^\s*(?P<term>.+)是什么\s*$"),
    re.compile(r"^\s*解释(?:一下)?(?P<term>.+)$"),
    re.compile(r"^\s*介绍(?:一下)?(?P<term>.+)$"),
    re.compile(r"^\s*请(?:你)?(?:讲讲|解释|介绍)(?P<term>.+)$"),
    re.compile(r"^\s*what\s+is\s+(?P<term>.+)$", re.IGNORECASE),
)
_STOP_TOKENS = {
    "什么",
    "一下",
    "这个",
    "那个",
    "一下子",
    "请问",
    "讲讲",
    "解释",
    "介绍",
    "定义",
    "概念",
    "一下吧",
}
_NO_EVIDENCE_PATTERNS = (
    "课件中没有直接覆盖该内容",
    "课件里没有直接覆盖该内容",
    "没有直接覆盖该内容",
)


def answer_question(request: QaAskTextRequest) -> QaAskTextResponse:
    start_at = time.perf_counter()
    evidence_context = _retrieve_evidence_context(request)

    if not evidence_context:
        answer = _answer_without_rag(request)
        return _build_response(answer, [], start_at)

    if not settings.LLM_API_KEY:
        logger.info(
            "LLM API key missing for QA. Use evidence template answer. coursewareId=%s sessionId=%s evidenceCount=%s",
            request.courseware_id,
            request.session_id,
            len(evidence_context),
        )
        return _build_response(_build_template_answer(evidence_context), evidence_context, start_at)

    try:
        answer = get_llm_client().invoke(_build_messages(request.question, request.page_index, evidence_context)).strip()
        if not answer:
            answer = _build_template_answer(evidence_context)

        answer, evidence_context = _maybe_switch_to_general_fallback(request, answer, evidence_context)

        logger.info(
            "RAG QA answered. coursewareId=%s sessionId=%s evidenceCount=%s evidencePages=%s fallbackToGeneral=%s",
            request.courseware_id,
            request.session_id,
            len(evidence_context),
            ",".join(str(item.get("page_index")) for item in evidence_context if item.get("page_index") is not None),
            not bool(evidence_context),
        )
        return _build_response(answer, evidence_context, start_at)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "RAG QA degraded to template answer. coursewareId=%s sessionId=%s reason=%s",
            request.courseware_id,
            request.session_id,
            str(exc),
        )
        return _build_response(_build_template_answer(evidence_context), evidence_context, start_at)


def stream_answer_events(request: QaAskTextRequest) -> Iterator[dict[str, object]]:
    evidence_context = _retrieve_evidence_context(request)
    yield _build_meta_event(evidence_context, request.page_index)

    if not evidence_context:
        logger.info(
            "RAG QA stream missing evidence. coursewareId=%s sessionId=%s",
            request.courseware_id,
            request.session_id,
        )
        yield from _simulate_stream_events(_answer_without_rag(request))
        return

    if not settings.LLM_API_KEY:
        logger.info(
            "LLM API key missing for QA stream. Use evidence template answer. coursewareId=%s sessionId=%s evidenceCount=%s",
            request.courseware_id,
            request.session_id,
            len(evidence_context),
        )
        yield from _simulate_stream_events(_build_template_answer(evidence_context))
        return

    try:
        answer = get_llm_client().invoke(_build_messages(request.question, request.page_index, evidence_context)).strip()
        if not answer:
            answer = _build_template_answer(evidence_context)

        answer, evidence_context = _maybe_switch_to_general_fallback(request, answer, evidence_context)
        yield from _simulate_stream_events(answer)
        logger.info(
            "RAG QA stream answered. coursewareId=%s sessionId=%s evidenceCount=%s fallbackToGeneral=%s",
            request.courseware_id,
            request.session_id,
            len(evidence_context),
            not bool(evidence_context),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "RAG QA stream degraded to template answer. coursewareId=%s sessionId=%s reason=%s",
            request.courseware_id,
            request.session_id,
            str(exc),
        )
        yield from _simulate_stream_events(_build_template_answer(evidence_context))


def _answer_without_rag(request: QaAskTextRequest) -> str:
    if not settings.LLM_API_KEY:
        return _NO_EVIDENCE_ANSWER

    try:
        answer = get_llm_client().invoke(_build_general_fallback_messages(request)).strip()
        if answer:
            logger.info(
                "QA answered by general LLM fallback. coursewareId=%s sessionId=%s pageIndex=%s",
                request.courseware_id,
                request.session_id,
                request.page_index,
            )
            return answer
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "General LLM fallback failed. coursewareId=%s sessionId=%s reason=%s",
            request.courseware_id,
            request.session_id,
            str(exc),
        )

    return _NO_EVIDENCE_ANSWER


def _retrieve_evidence_context(request: QaAskTextRequest) -> list[dict]:
    retrieved = retrieve_context(
        courseware_id=request.courseware_id,
        question=request.question,
        page_index=request.page_index,
        top_k=max(request.top_k + 2, request.top_k),
    )
    courseware_matches = _build_courseware_page_evidence(request)
    current_page_evidence = _build_current_page_evidence(request)

    merged = _merge_evidence(retrieved, courseware_matches, current_page_evidence)

    if _should_try_page_vision(request, merged):
        vision_evidence = _maybe_build_page_vision_evidence(request)
        if vision_evidence is not None:
            merged = _merge_evidence(merged, [vision_evidence])

    limited = _limit_evidence_by_page(merged, max(request.top_k + 2, request.top_k))
    return _filter_evidence_for_question(request.question, limited)


def _build_courseware_page_evidence(request: QaAskTextRequest) -> list[dict]:
    if not request.courseware_pages:
        return []

    visual_question = _is_visual_question(request.question)
    evidence: list[dict] = []
    for page in request.courseware_pages:
        page_text = _build_courseware_page_text(page, include_visual=visual_question)
        if not page_text:
            continue

        lexical_score = _keyword_overlap_score(request.question, page_text)
        if lexical_score <= 0:
            continue

        adjusted_score = lexical_score + _page_proximity_bonus(page.page_index, request.page_index)
        if visual_question and ((page.visual_summary or "").strip() or page.visual_objects):
            adjusted_score += 0.18

        evidence.append(
            {
                "chunk_id": f"{request.courseware_id}_p{page.page_index:03d}_courseware_page",
                "page_index": page.page_index,
                "text": page_text,
                "source": f"page_{page.page_index}",
                "score": lexical_score,
                "adjusted_score": adjusted_score,
                "metadata": {"source": "courseware_page"},
            }
        )

    evidence.sort(key=lambda item: (item["adjusted_score"], item["score"]), reverse=True)
    return _limit_evidence_by_page(evidence, max(request.top_k + 4, request.top_k))


def _build_courseware_page_text(page, *, include_visual: bool) -> str:
    parts = [
        page.title,
        page.content,
        f"知识点：{'、'.join(page.knowledge_points)}" if page.knowledge_points else "",
    ]

    if include_visual or not _join_text_parts(parts):
        if page.visual_summary:
            parts.append(f"视觉摘要：{page.visual_summary}")
        if page.visual_objects:
            parts.append(f"可见对象：{'、'.join(page.visual_objects)}")

    return _join_text_parts(parts)


def _build_current_page_evidence(request: QaAskTextRequest) -> list[dict]:
    if request.page_index is None:
        return []

    evidence: list[dict] = []
    current_page_text = _join_text_parts(
        [
            request.current_page_title,
            request.current_page_content,
            f"知识点：{'、'.join(request.current_page_knowledge_points)}" if request.current_page_knowledge_points else "",
        ]
    )
    if current_page_text:
        evidence.append(
            {
                "chunk_id": f"{request.courseware_id}_p{request.page_index:03d}_live_text",
                "page_index": request.page_index,
                "text": current_page_text,
                "source": f"page_{request.page_index}",
                "score": _CURRENT_PAGE_TEXT_SCORE,
                "adjusted_score": _CURRENT_PAGE_TEXT_SCORE,
                "metadata": {"source": "current_page_text"},
            }
        )

    visual_summary = (request.current_page_visual_summary or "").strip()
    if visual_summary:
        evidence.append(
            {
                "chunk_id": f"{request.courseware_id}_p{request.page_index:03d}_live_visual",
                "page_index": request.page_index,
                "text": f"视觉摘要：{visual_summary}",
                "source": f"page_{request.page_index}",
                "score": _CURRENT_PAGE_VISUAL_SCORE,
                "adjusted_score": _CURRENT_PAGE_VISUAL_SCORE + (0.18 if _is_visual_question(request.question) else 0.0),
                "metadata": {
                    "source": "visual_summary",
                    "visual_summary": visual_summary,
                    "visual_objects": request.current_page_visual_objects,
                },
            }
        )

    return evidence


def _should_try_page_vision(request: QaAskTextRequest, evidence_context: list[dict]) -> bool:
    if not (request.current_page_image_path or "").strip():
        return False
    if _is_visual_question(request.question):
        return True
    if evidence_context:
        return False
    return not (request.current_page_content or "").strip()


def _maybe_build_page_vision_evidence(request: QaAskTextRequest) -> dict | None:
    try:
        vision_answer = get_vision_client().answer_page_question(
            page_index=request.page_index or 1,
            question=request.question,
            image_path=request.current_page_image_path or "",
            hint_text=_join_text_parts(
                [
                    request.current_page_title,
                    request.current_page_content,
                    request.current_page_visual_summary,
                    "、".join(request.current_page_knowledge_points),
                ]
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Vision QA skipped. coursewareId=%s pageIndex=%s reason=%s",
            request.courseware_id,
            request.page_index,
            str(exc),
        )
        return None

    normalized_answer = " ".join(vision_answer.split()).strip()
    if not normalized_answer or any(pattern in normalized_answer for pattern in _NO_EVIDENCE_PATTERNS):
        return None

    return {
        "chunk_id": f"{request.courseware_id}_p{(request.page_index or 1):03d}_live_vision",
        "page_index": request.page_index,
        "text": normalized_answer,
        "source": f"page_{request.page_index}" if request.page_index is not None else "courseware",
        "score": 1.0,
        "adjusted_score": 1.4 if _is_visual_question(request.question) else 1.05,
        "metadata": {"source": "page_vision"},
    }


def _build_messages(question: str, page_index: int | None, evidence_context: list[dict]) -> list[SystemMessage | HumanMessage]:
    return [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=_build_user_prompt(question, page_index, evidence_context)),
    ]


def _build_general_fallback_messages(request: QaAskTextRequest) -> list[SystemMessage | HumanMessage]:
    lines = [
        f"学生问题：{request.question.strip()}",
        f"当前定位页：{request.page_index if request.page_index is not None else '未知'}",
    ]

    if request.current_page_title:
        lines.append(f"当前页标题：{request.current_page_title.strip()}")
    if request.current_page_content:
        lines.append(f"当前页正文：{request.current_page_content.strip()}")
    if request.current_page_knowledge_points:
        lines.append(f"当前页知识点：{'、'.join(request.current_page_knowledge_points)}")
    if request.current_page_visual_summary:
        lines.append(f"当前页视觉摘要：{request.current_page_visual_summary.strip()}")
    if request.current_page_visual_objects:
        lines.append(f"当前页可见对象：{'、'.join(request.current_page_visual_objects)}")

    courseware_hints = _build_courseware_hint_lines(request)
    if courseware_hints:
        lines.append("整份课件中与该问题更相关的页面概览：")
        lines.extend(courseware_hints)

    lines.append("当前没有检索到可直接引用的 RAG 证据，请基于以上课程线索和通用知识直接回答。")
    return [
        SystemMessage(content=_GENERAL_FALLBACK_SYSTEM_PROMPT),
        HumanMessage(content="\n".join(lines)),
    ]


def _build_courseware_hint_lines(request: QaAskTextRequest) -> list[str]:
    hints = _build_courseware_page_evidence(request)
    if not hints:
        return []

    limited = _limit_evidence_by_page(hints, _COURSEWARE_HINT_LIMIT)
    return [
        f"- 第 {item.get('page_index')} 页：{_trim_text(item.get('text', ''), limit=140)}"
        for item in limited
    ]


def _build_user_prompt(question: str, page_index: int | None, evidence_context: list[dict]) -> str:
    lines = [
        f"课堂提问：{question.strip()}",
        f"当前定位页：{page_index if page_index is not None else '未知'}",
        "回答范围：整份课件。当前定位页只表示学生此刻看到的位置，不要把答案限制在这一页。",
        "可用证据：",
    ]

    for index, item in enumerate(evidence_context, start=1):
        lines.append(
            f"{index}. 来源={item.get('source', 'courseware')} | 页码={item.get('page_index')} | "
            f"得分={item.get('adjusted_score', item.get('score', 0.0)):.2f}"
        )
        lines.append(f"证据内容：{_trim_text(item.get('text', ''))}")

    lines.append(
        "请综合这些课件证据作答；如果多个页面共同支持答案，可以合并说明。"
        "只有当整份课件都没有足够证据时，才回答“课件中没有直接覆盖该内容”。"
    )
    return "\n".join(lines)


def _build_template_answer(evidence_context: list[dict]) -> str:
    primary_evidence = evidence_context[0] if evidence_context else {}
    page_index = _safe_page_index(primary_evidence.get("page_index"))
    text = _trim_text(primary_evidence.get("text", ""), limit=160)

    if not text:
        return _NO_EVIDENCE_ANSWER

    if page_index is not None:
        return f"根据课件第 {page_index} 页及相关上下文，可以先这样理解：{text}"
    return f"根据当前课件内容，可以先这样回答：{text}"


def _maybe_switch_to_general_fallback(
    request: QaAskTextRequest,
    answer: str,
    evidence_context: list[dict],
) -> tuple[str, list[dict]]:
    normalized = " ".join(str(answer or "").split()).strip()
    if evidence_context and any(pattern in normalized for pattern in _NO_EVIDENCE_PATTERNS):
        fallback_answer = _answer_without_rag(request)
        if fallback_answer and fallback_answer != _NO_EVIDENCE_ANSWER:
            return fallback_answer, []
    return normalized or answer, evidence_context


def _build_response(answer: str, evidence_context: list[dict], start_at: float) -> QaAskTextResponse:
    latency_ms = max(1, int((time.perf_counter() - start_at) * 1000))
    return QaAskTextResponse(
        answer=answer.strip(),
        evidence=_build_response_evidence(evidence_context),
        latency_ms=latency_ms,
    )


def _build_response_evidence(evidence_context: list[dict]) -> list[QaEvidenceItem]:
    return [
        QaEvidenceItem(
            source=str(item.get("source") or "courseware"),
            text=str(item.get("text") or ""),
            page_index=_safe_page_index(item.get("page_index")),
            chunk_id=str(item.get("chunk_id")) if item.get("chunk_id") else None,
        )
        for item in evidence_context
        if str(item.get("text") or "").strip()
    ]


def _build_meta_event(evidence_context: list[dict], page_index: int | None) -> dict[str, object]:
    return {
        "type": "meta",
        "contextPageIndex": page_index,
        "scope": "courseware",
        "evidence": [item.model_dump(by_alias=True) for item in _build_response_evidence(evidence_context)],
    }


def _simulate_stream_events(answer: str) -> Iterator[dict[str, str]]:
    for chunk in _chunk_text_for_stream(answer):
        yield {"type": "delta", "content": chunk}


def _chunk_text_for_stream(answer: str) -> list[str]:
    normalized = " ".join(str(answer or "").split()).strip()
    if not normalized:
        return []
    return [
        normalized[index:index + _STREAM_FALLBACK_CHUNK_SIZE]
        for index in range(0, len(normalized), _STREAM_FALLBACK_CHUNK_SIZE)
    ]


def _merge_evidence(*groups: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen_keys: set[tuple[object, str]] = set()

    for group in groups:
        for item in group or []:
            text = _trim_text(item.get("text", ""), limit=240)
            if not text:
                continue
            key = (_safe_page_index(item.get("page_index")), text)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            normalized_item = dict(item)
            normalized_item["text"] = text
            normalized_item["page_index"] = _safe_page_index(item.get("page_index"))
            normalized_item["score"] = _safe_float(item.get("score"))
            normalized_item["adjusted_score"] = _safe_float(item.get("adjusted_score"), normalized_item["score"])
            merged.append(normalized_item)

    merged.sort(key=lambda item: (item["adjusted_score"], item["score"]), reverse=True)
    return merged


def _limit_evidence_by_page(evidence_context: list[dict], limit: int) -> list[dict]:
    if limit <= 0 or not evidence_context:
        return []

    selected: list[dict] = []
    overflow: list[dict] = []
    seen_pages: set[int | None] = set()

    for item in evidence_context:
        page_index = _safe_page_index(item.get("page_index"))
        if page_index not in seen_pages:
            seen_pages.add(page_index)
            selected.append(item)
        else:
            overflow.append(item)
        if len(selected) >= limit:
            return selected

    for item in overflow:
        if len(selected) >= limit:
            break
        selected.append(item)

    return selected


def _filter_evidence_for_question(question: str, evidence_context: list[dict]) -> list[dict]:
    if not evidence_context:
        return []

    focus_term = _extract_focus_term(question)
    if not focus_term:
        return evidence_context

    focus_tokens = _extract_focus_tokens(focus_term)
    if not focus_tokens:
        return evidence_context

    strong_matches: list[dict] = []
    for item in evidence_context:
        match_score = _focus_match_score(focus_term, focus_tokens, str(item.get("text") or ""))
        if match_score <= 0:
            continue
        normalized_item = dict(item)
        normalized_item["focus_match_score"] = match_score
        strong_matches.append(normalized_item)

    strong_matches.sort(
        key=lambda item: (
            _safe_float(item.get("focus_match_score")),
            _safe_float(item.get("adjusted_score")),
            _safe_float(item.get("score")),
        ),
        reverse=True,
    )
    return strong_matches


def _extract_focus_term(question: str) -> str | None:
    normalized = _strip_question_noise(question)
    if not normalized or _is_visual_question(normalized):
        return None

    for pattern in _DEFINITION_PATTERNS:
        match = pattern.match(normalized)
        if not match:
            continue
        candidate = _strip_focus_term(match.group("term"))
        if candidate:
            return candidate

    return None


def _strip_question_noise(question: str) -> str:
    normalized = " ".join(str(question or "").split()).strip()
    return normalized.strip("，。！？?!.：:；;、")


def _strip_focus_term(term: str) -> str:
    normalized = _strip_question_noise(term)
    normalized = re.sub(r"^(一下|一个|这个|那个|关于)", "", normalized)
    normalized = re.sub(r"(的定义|这个概念|这个问题|这一点)$", "", normalized)
    normalized = normalized.strip("“”\"'（）()[]【】 ")
    return normalized or ""


def _extract_focus_tokens(term: str) -> list[str]:
    tokens: list[str] = []
    for token in _tokenize(term.lower()):
        normalized = token.strip().lower()
        if not normalized or normalized in _STOP_TOKENS:
            continue
        if re.fullmatch(r"[a-z0-9_]+", normalized):
            if len(normalized) < 3:
                continue
        elif len(normalized) < 2:
            continue
        tokens.append(normalized)

    deduped: list[str] = []
    seen: set[str] = set()
    for token in sorted(tokens, key=len, reverse=True):
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


def _focus_match_score(focus_term: str, focus_tokens: list[str], text: str) -> float:
    normalized_text = _normalize_match_text(text)
    normalized_term = _normalize_match_text(focus_term)
    if not normalized_text or not normalized_term:
        return 0.0

    exact_match = normalized_term in normalized_text
    matched_tokens = [token for token in focus_tokens if _normalize_match_text(token) in normalized_text]

    if exact_match:
        return 10.0 + len(matched_tokens)

    required_matches = max(2, math.ceil(len(focus_tokens) * 0.4))
    if len(matched_tokens) >= required_matches:
        return float(len(matched_tokens))

    return 0.0


def _normalize_match_text(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", str(text or "").lower())


def _page_proximity_bonus(candidate_page_index: int | None, current_page_index: int | None) -> float:
    if candidate_page_index is None or current_page_index is None:
        return 0.0
    if candidate_page_index == current_page_index:
        return 0.10
    if abs(candidate_page_index - current_page_index) == 1:
        return 0.04
    return 0.0


def _keyword_overlap_score(query: str, content: str) -> float:
    query_lower = (query or "").lower().strip()
    content_lower = (content or "").lower()
    if not query_lower or not content_lower:
        return 0.0

    score = 2.2 if query_lower in content_lower else 0.0
    for token in _tokenize(query_lower):
        if token and token in content_lower:
            score += 1.0
    return score


def _tokenize(text: str) -> list[str]:
    raw_tokens = [token for token in _TOKEN_PATTERN.findall(text) if token]
    if not raw_tokens:
        return []

    expanded: list[str] = []
    for token in raw_tokens:
        expanded.append(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            if len(token) >= 2:
                expanded.extend(token[index:index + 2] for index in range(0, len(token) - 1))
            if len(token) >= 4:
                expanded.extend(token[index:index + 3] for index in range(0, len(token) - 2))

    seen: set[str] = set()
    result: list[str] = []
    for item in expanded:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _join_text_parts(parts: list[str | None]) -> str:
    return " ".join(part.strip() for part in parts if isinstance(part, str) and part.strip()).strip()


def _trim_text(text: str, limit: int = 220) -> str:
    normalized = " ".join(str(text or "").split()).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def _safe_page_index(page_index: object) -> int | None:
    try:
        resolved = int(page_index)
    except (TypeError, ValueError):
        return None
    return resolved if resolved > 0 else None


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_visual_question(question: str) -> bool:
    normalized = (question or "").strip()
    if not normalized:
        return False
    return bool(_VISUAL_QUESTION_PATTERN.search(normalized))
