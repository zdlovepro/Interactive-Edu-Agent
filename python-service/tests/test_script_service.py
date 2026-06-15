from __future__ import annotations

import re

import pytest

from app.clients import llm_client as llm_client_module
from app.core.config import settings
from app.core.exceptions import ModelOutputException
from app.schemas.script import PageContent, ScriptGenerateRequest, ScriptGenerateResponse
from app.services import script_service
from app.services.script_service import extract_json_payload, generate_script, parse_model_output


def _build_request(
    *,
    subject: str | None = "计算机科学",
    pages: list[PageContent] | None = None,
) -> ScriptGenerateRequest:
    return ScriptGenerateRequest(
        courseware_id="cware_script_1",
        courseware_name="递归示例",
        subject=subject,
        pages=pages
        or [
            PageContent(
                page_index=1,
                title="递归定义",
                text_content="递归是函数直接或间接调用自身的一种方法，通常需要有终止条件来避免无限展开。",
                keywords=["递归", "终止条件"],
            )
        ],
    )


def test_extract_json_payload_supports_pure_json():
    raw_output = """
    {
      "courseware_id": "cware_script_1",
      "opening": "开场",
      "pages": [{"page_index": 1, "script": "讲解", "transition": ""}],
      "closing": "结尾"
    }
    """

    extracted = extract_json_payload(raw_output)

    assert extracted.startswith("{")
    assert '"courseware_id": "cware_script_1"' in extracted


def test_extract_json_payload_supports_json_fence():
    raw_output = """```json
{
  "courseware_id": "cware_script_1",
  "opening": "开场",
  "pages": [{"page_index": 1, "script": "讲解", "transition": ""}],
  "closing": "结尾"
}
```"""

    extracted = extract_json_payload(raw_output)

    assert extracted.startswith("{")
    assert '"opening": "开场"' in extracted


def test_extract_json_payload_supports_explanatory_text():
    raw_output = """
    下面是整理后的 JSON，请直接使用：
    {
      "courseware_id": "cware_script_1",
      "opening": "开场",
      "pages": [{"page_index": 1, "script": "讲解", "transition": ""}],
      "closing": "结尾"
    }
    以上就是结果。
    """

    extracted = extract_json_payload(raw_output)

    assert extracted.startswith("{")
    assert extracted.endswith("}")
    assert '"pages":' in extracted


def test_extract_json_payload_non_json_returns_stripped_text():
    raw_output = "这不是 JSON，只是一段解释文字。"

    extracted = extract_json_payload(raw_output)

    assert extracted == raw_output


def test_parse_model_output_repairs_multiline_string_and_backfills_missing_page():
    request = _build_request(
        pages=[
            PageContent(
                page_index=1,
                title="递归定义",
                text_content="递归是函数直接或间接调用自身的一种方法，通常需要有终止条件。",
                keywords=["递归", "终止条件"],
            ),
            PageContent(
                page_index=2,
                title="卷积层例题",
                text_content="Input volume: 32x32x3 10 filters 5x5 stride 1 pad 2 Output volume size: ?",
                keywords=["卷积", "输出尺寸"],
            ),
        ]
    )
    raw_output = """
    {
      "courseware_id": "wrong_id",
      "opening": "同学们好，我们先建立整体认识。",
      "pages": [
        {
          "page_index": 1,
          "script": "递归的核心在于问题会被拆成结构相同的子问题。
同时必须设置终止条件，否则调用会一直展开。",
          "transition": "下一页我们继续看"
        }
      ],
      "closing": "今天的内容就梳理到这里。"
    }
    """

    result = parse_model_output(raw_output, request)

    assert result.courseware_id == "cware_script_1"
    assert len(result.pages) == 2
    assert result.pages[0].page_index == 1
    assert "终止条件" in result.pages[0].script
    assert result.pages[0].transition == ""
    assert result.pages[1].page_index == 2
    assert "输出尺寸" in result.pages[1].script


def test_parse_model_output_non_json_raises_model_output_exception():
    with pytest.raises(ModelOutputException, match="合法 JSON"):
        parse_model_output("not json at all", _build_request())


def test_generate_script_falls_back_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(llm_client_module, "_llm_client", None)

    result = generate_script(_build_request())

    assert isinstance(result, ScriptGenerateResponse)
    assert result.courseware_id == "cware_script_1"
    assert "递归" in result.opening
    assert "递归定义" in result.pages[0].script
    assert "现在我们来看第" not in result.pages[0].script
    assert result.closing


def test_generate_script_uses_general_subject_when_subject_missing(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(llm_client_module, "_llm_client", None)

    result = generate_script(_build_request(subject=None))

    assert result.opening
    assert "通用课程" not in result.opening


def test_generate_script_fallback_handles_blank_page_text_without_page_filler(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(llm_client_module, "_llm_client", None)

    request = _build_request(
        pages=[
            PageContent(
                page_index=1,
                title="课程导入",
                text_content="   ",
                keywords=["学习目标", "课程导入"],
            )
        ]
    )

    result = generate_script(request)

    assert "现在我们来看第" not in result.pages[0].script
    assert "课程导入" in result.pages[0].script


def test_generate_script_fallback_turns_english_cnn_slide_into_chinese_explanation(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(llm_client_module, "_llm_client", None)

    request = _build_request(
        pages=[
            PageContent(
                page_index=1,
                title="Convolution Layer: Example",
                text_content="Input volume: 32x32x3\n10 5x5 filters with stride 1, pad 2\nOutput volume size: ?",
                keywords=["Convolution Layer", "output size"],
            )
        ]
    )

    result = generate_script(request)

    assert "输出尺寸" in result.pages[0].script
    assert "卷积层" in result.pages[0].script
    assert "现在我们来看第" not in result.pages[0].script
    assert "Machine Learning" not in result.pages[0].script


def test_generate_script_fallback_keeps_low_value_page_short(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(llm_client_module, "_llm_client", None)

    request = _build_request(
        pages=[
            PageContent(
                page_index=1,
                title="Upload your answer to",
                text_content="Upload your answer to",
                keywords=["upload"],
            )
        ]
    )

    result = generate_script(request)

    assert "练习" in result.pages[0].script
    assert len(result.pages[0].script) < 80
    assert "重点关注" not in result.pages[0].script


def test_generate_script_prompt_contains_json_constraints_and_examples(monkeypatch):
    captured: dict[str, str] = {}

    class _FakeLLMClient:
        def invoke(self, messages, *, temperature=None, max_tokens=None):
            captured["system"] = messages[0].content
            captured["human"] = messages[1].content
            captured["temperature"] = str(temperature)
            return """
            {
              "courseware_id": "ignored-by-parser",
              "opening": "这节内容重点讲递归的核心思路。",
              "pages": [
                {
                  "page_index": 1,
                  "script": "递归的关键是把问题拆成结构相同的子问题，并且一定要有终止条件。",
                  "transition": ""
                },
                {
                  "page_index": 2,
                  "script": "调用栈会随着递归展开，再随着结果返回逐层收拢。",
                  "transition": ""
                }
              ],
              "closing": "这部分内容先梳理到这里。"
            }
            """

    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(script_service, "get_llm_client", lambda: _FakeLLMClient())

    request = _build_request(
        subject=None,
        pages=[
            PageContent(
                page_index=1,
                title="递归定义",
                text_content="递归是函数直接或间接调用自身的一种方法。",
                keywords=["递归", "终止条件"],
            ),
            PageContent(
                page_index=2,
                title="执行过程",
                text_content="调用栈会随着递归层级不断展开，再逐层返回。",
                keywords=["调用栈", "返回"],
            ),
        ],
    )

    result = generate_script(request)

    assert isinstance(result, ScriptGenerateResponse)
    assert ScriptGenerateResponse.model_validate(result.model_dump()) == result
    assert "只输出合法 JSON" in captured["system"]
    assert "不要出现半角双引号" in captured["system"]
    assert "总页数：2" in captured["human"]
    assert "学科：通用课程" in captured["human"]
    assert "错误示例 1" in captured["human"]
    assert "禁止写法与修正方向" in captured["human"]
    assert "title: 递归定义" in captured["human"]
    assert "clean_text: 递归是函数直接或间接调用自身的一种方法" in captured["human"]
    assert captured["temperature"] == "0.0"


def test_generate_script_retries_chunk_with_retry_prompt(monkeypatch):
    captured_humans: list[str] = []

    class _FakeLLMClient:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, messages, *, temperature=None, max_tokens=None):
            self.calls += 1
            captured_humans.append(messages[1].content)
            if self.calls == 1:
                return "not json"
            return """
            {
              "pages": [
                {
                  "page_index": 1,
                  "script": "递归的关键是把问题拆成结构相同的子问题，同时一定要设置终止条件。",
                  "transition": ""
                },
                {
                  "page_index": 2,
                  "script": "调用栈会随着递归展开，再在结果返回时逐层收拢，这样整个求解过程才完整闭合。",
                  "transition": ""
                }
              ]
            }
            """

    fake_client = _FakeLLMClient()
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(script_service, "get_llm_client", lambda: fake_client)

    request = _build_request(
        pages=[
            PageContent(
                page_index=1,
                title="递归定义",
                text_content="递归是函数直接或间接调用自身的一种方法。",
                keywords=["递归", "终止条件"],
            ),
            PageContent(
                page_index=2,
                title="执行过程",
                text_content="调用栈会随着递归层级不断展开，再逐层返回。",
                keywords=["调用栈", "返回"],
            ),
        ],
    )

    result = generate_script(request)

    assert fake_client.calls == 2
    assert len(captured_humans) == 2
    assert "上一轮输出没有通过校验" in captured_humans[1]
    assert "错误示例" in captured_humans[1]
    assert "递归的关键" in result.pages[0].script
    assert "调用栈" in result.pages[1].script


def test_generate_script_splits_chunk_after_retry_exhausted(monkeypatch):
    monkeypatch.setattr(script_service, "SCRIPT_PAGE_CHUNK_SIZE", 2)
    captured_humans: list[str] = []

    class _FakeLLMClient:
        def __init__(self) -> None:
            self.calls = 0

        def invoke(self, messages, *, temperature=None, max_tokens=None):
            self.calls += 1
            human = messages[1].content
            captured_humans.append(human)
            if self.calls <= 2:
                return "not json"

            match = re.search(r"--- page (\d+) /", human)
            page_index = int(match.group(1))
            return f"""
            {{
              "pages": [
                {{
                  "page_index": {page_index},
                  "script": "第{page_index}个知识点重点是理解递归调用和返回之间的对应关系，真正要掌握的是问题拆解与收敛逻辑。",
                  "transition": ""
                }}
              ]
            }}
            """

    fake_client = _FakeLLMClient()
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(script_service, "get_llm_client", lambda: fake_client)

    request = _build_request(
        pages=[
            PageContent(
                page_index=1,
                title="递归定义",
                text_content="递归是函数直接或间接调用自身的一种方法。",
                keywords=["递归", "终止条件"],
            ),
            PageContent(
                page_index=2,
                title="执行过程",
                text_content="调用栈会随着递归层级不断展开，再逐层返回。",
                keywords=["调用栈", "返回"],
            ),
        ],
    )

    result = generate_script(request)

    assert fake_client.calls == 4
    assert any("第 1.1 批" in human for human in captured_humans)
    assert any("第 1.2 批" in human for human in captured_humans)
    assert len(result.pages) == 2
    assert "问题拆解" in result.pages[0].script
    assert "收敛逻辑" in result.pages[1].script


def test_refine_teacher_style_rewrites_english_slide_reading_to_chinese():
    refined = script_service._refine_teacher_style_script(
        "Convolution layer computes activation map with 5x5 filter and stride 1.",
        title="Convolution Layer: Example",
        text_content="Input volume: 32x32x3 10 filters 5x5 stride 1 pad 2 Output volume size: ?",
        keywords=["Convolution Layer", "output size"],
        page_role="formula_detail",
    )

    assert "卷积层" in refined
    assert "输出尺寸" in refined or "步长" in refined
    assert not script_service._is_mostly_english(refined)


def test_generate_script_cleans_model_filler_and_transition(monkeypatch):
    class _FakeLLMClient:
        def invoke(self, _messages, *, temperature=None, max_tokens=None):
            return """
            {
              "courseware_id": "ignored-by-parser",
              "opening": "这节内容主要讲卷积层。",
              "pages": [
                {
                  "page_index": 1,
                  "script": "这一页主要在讲卷积层怎样提取局部特征。下一页我们继续看输出尺寸。",
                  "transition": "理解完我们继续下一页"
                }
              ],
              "closing": "这部分内容先讲到这里。"
            }
            """

    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(script_service, "get_llm_client", lambda: _FakeLLMClient())

    request = _build_request(
        pages=[
            PageContent(
                page_index=1,
                title="Convolution Layer",
                text_content="32x32x3 image 5x5x3 filter dot product activation map",
                keywords=["convolution", "filter"],
            )
        ]
    )

    result = generate_script(request)

    assert "下一页" not in result.pages[0].script
    assert "这一页主要在讲" not in result.pages[0].script
    assert result.pages[0].transition == ""
    assert "卷积层" in result.pages[0].script


def test_generate_script_endpoint_returns_base_response_when_api_key_missing(request_app, monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    monkeypatch.setattr(llm_client_module, "_llm_client", None)

    response = request_app(
        "POST",
        "/python/v1/script/generate",
        json={
            "coursewareId": "cware_script_api",
            "coursewareName": "链表示例",
            "subject": "",
            "pages": [
                {
                    "pageIndex": 1,
                    "title": "链表结构",
                    "textContent": "链表由节点组成，每个节点包含数据和指针。",
                    "keywords": ["节点", "指针"],
                }
            ],
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["code"] == 0
    assert payload["message"] == "success"
    assert payload["data"]["courseware_id"] == "cware_script_api"
    assert payload["data"]["pages"][0]["page_index"] == 1
    assert payload["data"]["pages"][0]["script"]


def test_generate_script_endpoint_returns_base_response_when_model_output_invalid(request_app, monkeypatch):
    class _FakeLLMClient:
        def invoke(self, _messages, *, temperature=None, max_tokens=None):
            return "不是 JSON"

    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(script_service, "get_llm_client", lambda: _FakeLLMClient())

    response = request_app(
        "POST",
        "/python/v1/script/generate",
        json={
            "coursewareId": "cware_script_api_bad",
            "coursewareName": "图示示例",
            "subject": "数学",
            "pages": [
                {
                    "pageIndex": 1,
                    "title": "基本概念",
                    "textContent": "这一页介绍基本概念。",
                    "keywords": ["概念"],
                }
            ],
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["code"] == 0
    assert payload["message"] == "success"
    assert payload["data"]["courseware_id"] == "cware_script_api_bad"
    assert payload["data"]["opening"]
    assert payload["data"]["pages"][0]["script"]
    assert payload["data"]["closing"]
