from __future__ import annotations

import asyncio

import httpx

from app.api.v1 import qa as qa_api
from app.core.config import settings
from app.main import app
from app.schemas.qa import QaAskTextRequest, QaAskTextResponse
from app.services import rag_service


def _build_request(**overrides) -> QaAskTextRequest:
    payload = {
        "sessionId": "sess_qa_1",
        "coursewareId": "cware_qa_1",
        "pageIndex": 3,
        "question": "这一页在讲什么",
        "topK": 5,
        "currentPageTitle": "线性回归",
        "currentPageContent": "这一页主要介绍线性回归的定义和损失函数。",
        "currentPageImagePath": "D:/mock/page3.png",
        "currentPageVisualSummary": "页面包含散点图和拟合直线。",
        "currentPageKnowledgePoints": ["定义", "损失函数"],
        "currentPageVisualObjects": ["散点图", "直线"],
    }
    payload.update(overrides)
    return QaAskTextRequest(**payload)


def _sample_evidence(page_index: int = 3, text: str = "这一页补充了线性回归的训练目标。") -> list[dict]:
    return [
        {
            "chunk_id": f"cware_qa_1_p{page_index:03d}_c000",
            "page_index": page_index,
            "text": text,
            "source": f"page_{page_index}",
            "score": 0.82,
            "adjusted_score": 1.12,
            "metadata": {"page_index": page_index},
        }
    ]


def _collect_sse_lines(method: str, path: str, json_body: dict | None = None) -> list[str]:
    async def _run() -> list[str]:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            async with client.stream(method, path, json=json_body) as response:
                assert response.status_code == 200
                return [line async for line in response.aiter_lines() if line]

    return asyncio.run(_run())


def test_answer_question_uses_current_page_context_when_retrieval_is_empty(monkeypatch):
    monkeypatch.setattr(rag_service, "retrieve_context", lambda **kwargs: [])
    monkeypatch.setattr(settings, "LLM_API_KEY", "")

    result = rag_service.answer_question(_build_request())

    assert isinstance(result, QaAskTextResponse)
    assert "线性回归的定义和损失函数" in result.answer
    assert result.evidence
    assert result.evidence[0].page_index == 3


def test_answer_question_uses_llm_when_evidence_available(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(rag_service, "retrieve_context", lambda **kwargs: _sample_evidence())

    class _FakeLLMClient:
        def invoke(self, messages):
            assert "课堂提问：这一页在讲什么" in messages[1].content
            assert "可用证据：" in messages[1].content
            return "这一页重点在于说明线性回归如何定义误差。"

    monkeypatch.setattr(rag_service, "get_llm_client", lambda: _FakeLLMClient())

    result = rag_service.answer_question(_build_request())

    assert result.answer == "这一页重点在于说明线性回归如何定义误差。"
    assert result.evidence[0].page_index == 3


def test_answer_question_uses_general_llm_fallback_when_no_rag_evidence(monkeypatch):
    monkeypatch.setattr(rag_service, "retrieve_context", lambda **kwargs: [])
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")

    class _FakeLLMClient:
        def invoke(self, messages):
            assert "当前没有检索到可直接引用的 RAG 证据" in messages[1].content
            assert "学生问题：什么是过拟合" in messages[1].content
            return "下面给出通用解释：过拟合是模型在训练集上表现很好，但在新数据上泛化较差。"

    monkeypatch.setattr(rag_service, "get_llm_client", lambda: _FakeLLMClient())

    result = rag_service.answer_question(
        _build_request(
            question="什么是过拟合",
            currentPageTitle="",
            currentPageContent="",
            currentPageVisualSummary="",
            currentPageKnowledgePoints=[],
            currentPageVisualObjects=[],
            currentPageImagePath="",
        )
    )

    assert "过拟合" in result.answer
    assert result.evidence == []


def test_answer_question_filters_weak_focus_matches_and_uses_general_llm(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        rag_service,
        "retrieve_context",
        lambda **kwargs: [
            {
                "chunk_id": "cware_qa_1_p013_c000",
                "page_index": 13,
                "text": "梯度下降会沿着损失函数的负梯度方向更新参数，向量方向决定更新路径。",
                "source": "page_13",
                "score": 2.8,
                "adjusted_score": 2.95,
            }
        ],
    )

    class _FakeLLMClient:
        def invoke(self, messages):
            assert "当前没有检索到可直接引用的 RAG 证据" in messages[1].content
            assert "学生问题：什么是支持向量机" in messages[1].content
            return "下面给出通用解释：支持向量机是一类通过最大化分类间隔来进行分类或回归的监督学习模型。"

    monkeypatch.setattr(rag_service, "get_llm_client", lambda: _FakeLLMClient())

    result = rag_service.answer_question(
        _build_request(
            question="什么是支持向量机",
            currentPageTitle="Topics",
            currentPageContent="本页只列出回归、线性回归、梯度下降等主题。",
            currentPageKnowledgePoints=["回归", "梯度下降"],
        )
    )

    assert "支持向量机" in result.answer
    assert result.evidence == []


def test_answer_question_keeps_matching_focus_evidence(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(
        rag_service,
        "retrieve_context",
        lambda **kwargs: _sample_evidence(page_index=12, text="过拟合指模型过度贴合训练数据，导致泛化能力下降。"),
    )

    result = rag_service.answer_question(
        _build_request(
            question="什么是过拟合",
            currentPageTitle="模型评估",
            currentPageContent="我们会讨论欠拟合和过拟合。",
        )
    )

    assert result.evidence
    assert result.evidence[0].page_index == 12
    assert "过拟合" in result.answer


def test_answer_question_can_use_page_vision_for_visual_question(monkeypatch):
    monkeypatch.setattr(rag_service, "retrieve_context", lambda **kwargs: [])
    monkeypatch.setattr(settings, "LLM_API_KEY", "")

    class _FakeVisionClient:
        def answer_page_question(self, **kwargs):
            assert kwargs["page_index"] == 3
            assert "图" in kwargs["question"]
            return "图里展示的是散点分布以及一条拟合直线。"

    monkeypatch.setattr(rag_service, "get_vision_client", lambda: _FakeVisionClient())

    result = rag_service.answer_question(_build_request(question="这张图在表达什么"))

    assert "散点分布" in result.answer
    assert any("拟合直线" in item.text for item in result.evidence)


def test_stream_answer_events_emit_meta_before_delta(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(rag_service, "retrieve_context", lambda **kwargs: _sample_evidence())

    events = list(rag_service.stream_answer_events(_build_request()))

    assert events[0]["type"] == "meta"
    assert events[0]["contextPageIndex"] == 3
    assert events[0]["evidence"]
    assert any(event["type"] == "delta" for event in events[1:])


def test_stream_answer_events_use_general_llm_fallback_when_no_evidence(monkeypatch):
    monkeypatch.setattr(rag_service, "retrieve_context", lambda **kwargs: [])
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")

    class _FakeLLMClient:
        def invoke(self, messages):
            assert "当前没有检索到可直接引用的 RAG 证据" in messages[1].content
            return "下面给出通用解释：欠拟合通常意味着模型表达能力不足或训练不充分。"

    monkeypatch.setattr(rag_service, "get_llm_client", lambda: _FakeLLMClient())

    events = list(
        rag_service.stream_answer_events(
            _build_request(
                question="什么是欠拟合",
                currentPageTitle="",
                currentPageContent="",
                currentPageVisualSummary="",
                currentPageKnowledgePoints=[],
                currentPageVisualObjects=[],
                currentPageImagePath="",
            )
        )
    )

    assert events[0]["type"] == "meta"
    assert events[0]["evidence"] == []
    assert "".join(event["content"] for event in events[1:] if event["type"] == "delta").startswith("下面给出通用解释")


def test_qa_request_accepts_camel_case_fields(request_app, monkeypatch):
    captured = {}

    def fake_answer_question(request: QaAskTextRequest) -> QaAskTextResponse:
        captured["session_id"] = request.session_id
        captured["courseware_id"] = request.courseware_id
        captured["page_index"] = request.page_index
        captured["current_page_title"] = request.current_page_title
        return QaAskTextResponse(
            answer="这是一个关于线性回归的页面。",
            evidence=[],
            latency_ms=12,
        )

    monkeypatch.setattr(qa_api, "answer_question", fake_answer_question)

    response = request_app(
        "POST",
        "/python/v1/qa/ask-text",
        json=_build_request().model_dump(by_alias=True),
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["code"] == 0
    assert payload["message"] == "success"
    assert payload["data"]["latencyMs"] == 12
    assert captured == {
        "session_id": "sess_qa_1",
        "courseware_id": "cware_qa_1",
        "page_index": 3,
        "current_page_title": "线性回归",
    }


def test_qa_stream_get_endpoint_returns_meta_and_done(monkeypatch):
    monkeypatch.setattr(
        qa_api,
        "stream_answer_events",
        lambda request: iter(
            [
                {"type": "meta", "contextPageIndex": request.page_index, "evidence": []},
                {"type": "delta", "content": f"answer:{request.courseware_id}"},
            ]
        ),
    )

    lines = _collect_sse_lines("GET", "/python/v1/qa/stream?coursewareId=cware_stream_1&question=流式输出&pageIndex=4")

    assert lines[0] == 'data: {"type": "meta", "contextPageIndex": 4, "evidence": []}'
    assert any('"type": "delta"' in line for line in lines)
    assert lines[-1] == 'data: {"type": "done"}'


def test_qa_stream_post_endpoint_accepts_json_body(monkeypatch):
    monkeypatch.setattr(
        qa_api,
        "stream_answer_events",
        lambda request: iter(
            [
                {"type": "meta", "contextPageIndex": request.page_index, "evidence": []},
                {"type": "delta", "content": "post-stream"},
            ]
        ),
    )

    lines = _collect_sse_lines(
        "POST",
        "/python/v1/qa/stream",
        json_body=_build_request(pageIndex=5).model_dump(by_alias=True),
    )

    assert lines[0] == 'data: {"type": "meta", "contextPageIndex": 5, "evidence": []}'
    assert any("post-stream" in line for line in lines)
    assert lines[-1] == 'data: {"type": "done"}'
