"""
讲稿 JSON 解析与业务校验测试。

测试目标
========
验证 app.services.script_json_parser.parse_script_response_from_llm 是否能：

1. 解析合法讲稿 JSON；
2. 接受 Markdown fenced JSON；
3. 自动补齐缺失的 courseware_id；
4. 拒绝 courseware_id 不一致；
5. 拒绝缺字段；
6. 拒绝额外字段；
7. 拒绝空字符串字段；
8. 拒绝 page_index 为 0；
9. 拒绝页数不一致；
10. 拒绝页码集合不一致；
11. 拒绝页码重复；
12. 对输出页顺序做归一化排序。
"""

from __future__ import annotations

import json

import pytest

from app.schemas.script import (
    PageContent,
    ScriptGenerateRequest,
)
from app.services.script_json_parser import (
    ScriptJsonParseError,
    parse_script_response_from_llm,
)


def _build_request() -> ScriptGenerateRequest:
    """构造标准两页讲稿生成请求。"""
    return ScriptGenerateRequest(
        courseware_id="cware_001",
        courseware_name="数据结构导论",
        subject="计算机科学",
        pages=[
            PageContent(
                page_index=1,
                title="递归简介",
                text_content="递归是函数直接或间接调用自身的编程技术，需要有终止条件。",
                keywords=["递归", "终止条件"],
            ),
            PageContent(
                page_index=2,
                title="斐波那契数列",
                text_content="斐波那契数列是递归的典型应用。",
                keywords=["斐波那契", "递归"],
            ),
        ],
    )


def _build_valid_payload() -> dict:
    """构造标准合法 LLM 输出 payload。"""
    return {
        "courseware_id": "cware_001",
        "opening": "大家好，欢迎来到数据结构导论的学习。",
        "pages": [
            {
                "page_index": 1,
                "script": "首先我们来看递归的基本概念。",
                "transition": "理解递归之后，我们继续看一个经典案例。",
            },
            {
                "page_index": 2,
                "script": "斐波那契数列是递归思想的典型体现。",
                "transition": "以上就是本页内容的小结。",
            },
        ],
        "closing": "本节课我们学习了递归及其典型应用。",
    }


def _to_raw_json(payload: dict) -> str:
    """将 payload 转为 JSON 字符串，保留中文。"""
    return json.dumps(payload, ensure_ascii=False)


def test_parse_valid_script_json_success() -> None:
    """标准合法讲稿 JSON 应解析成功。"""
    request = _build_request()
    raw_output = _to_raw_json(_build_valid_payload())

    result = parse_script_response_from_llm(
        raw_output=raw_output,
        request=request,
    )

    assert result.courseware_id == "cware_001"
    assert result.opening == "大家好，欢迎来到数据结构导论的学习。"
    assert len(result.pages) == 2
    assert result.pages[0].page_index == 1
    assert result.pages[1].page_index == 2
    assert result.closing == "本节课我们学习了递归及其典型应用。"


def test_parse_markdown_fenced_script_json_success() -> None:
    """Markdown fenced JSON 应解析成功。"""
    request = _build_request()
    raw_output = "```json\n" + _to_raw_json(_build_valid_payload()) + "\n```"

    result = parse_script_response_from_llm(
        raw_output=raw_output,
        request=request,
    )

    assert result.courseware_id == "cware_001"
    assert len(result.pages) == 2


def test_missing_courseware_id_should_be_filled_from_request() -> None:
    """如果大模型没有输出 courseware_id，可以从请求中补齐。"""
    request = _build_request()
    payload = _build_valid_payload()
    payload.pop("courseware_id")

    result = parse_script_response_from_llm(
        raw_output=_to_raw_json(payload),
        request=request,
    )

    assert result.courseware_id == request.courseware_id


def test_mismatched_courseware_id_should_fail() -> None:
    """如果大模型输出了错误 courseware_id，应判定失败，而不是静默覆盖。"""
    request = _build_request()
    payload = _build_valid_payload()
    payload["courseware_id"] = "another_courseware"

    with pytest.raises(ScriptJsonParseError) as exc_info:
        parse_script_response_from_llm(
            raw_output=_to_raw_json(payload),
            request=request,
        )

    assert exc_info.value.code == "SCRIPT_JSON_COURSEWARE_ID_MISMATCH"


def test_missing_required_field_should_fail() -> None:
    """缺少必填字段 opening 应失败。"""
    request = _build_request()
    payload = _build_valid_payload()
    payload.pop("opening")

    with pytest.raises(ScriptJsonParseError) as exc_info:
        parse_script_response_from_llm(
            raw_output=_to_raw_json(payload),
            request=request,
        )

    assert exc_info.value.code == "SCRIPT_JSON_SCHEMA_INVALID"


def test_extra_field_should_fail() -> None:
    """大模型输出额外字段应失败。"""
    request = _build_request()
    payload = _build_valid_payload()
    payload["summary"] = "这是模型额外生成的字段。"

    with pytest.raises(ScriptJsonParseError) as exc_info:
        parse_script_response_from_llm(
            raw_output=_to_raw_json(payload),
            request=request,
        )

    assert exc_info.value.code == "SCRIPT_JSON_SCHEMA_INVALID"


def test_extra_field_inside_page_should_fail() -> None:
    """pages[] 内部输出额外字段也应失败。"""
    request = _build_request()
    payload = _build_valid_payload()
    payload["pages"][0]["duration"] = 12

    with pytest.raises(ScriptJsonParseError) as exc_info:
        parse_script_response_from_llm(
            raw_output=_to_raw_json(payload),
            request=request,
        )

    assert exc_info.value.code == "SCRIPT_JSON_SCHEMA_INVALID"


def test_empty_script_should_fail() -> None:
    """pages[].script 为空字符串应失败。"""
    request = _build_request()
    payload = _build_valid_payload()
    payload["pages"][0]["script"] = ""

    with pytest.raises(ScriptJsonParseError) as exc_info:
        parse_script_response_from_llm(
            raw_output=_to_raw_json(payload),
            request=request,
        )

    assert exc_info.value.code == "SCRIPT_JSON_SCHEMA_INVALID"


def test_blank_transition_should_fail() -> None:
    """pages[].transition 仅包含空白字符应失败。"""
    request = _build_request()
    payload = _build_valid_payload()
    payload["pages"][0]["transition"] = "   "

    with pytest.raises(ScriptJsonParseError) as exc_info:
        parse_script_response_from_llm(
            raw_output=_to_raw_json(payload),
            request=request,
        )

    assert exc_info.value.code == "SCRIPT_JSON_SCHEMA_INVALID"


def test_page_index_zero_should_fail() -> None:
    """page_index 为 0 应失败。"""
    request = _build_request()
    payload = _build_valid_payload()
    payload["pages"][0]["page_index"] = 0

    with pytest.raises(ScriptJsonParseError) as exc_info:
        parse_script_response_from_llm(
            raw_output=_to_raw_json(payload),
            request=request,
        )

    assert exc_info.value.code == "SCRIPT_JSON_SCHEMA_INVALID"


def test_page_count_mismatch_should_fail() -> None:
    """响应页数少于请求页数应失败。"""
    request = _build_request()
    payload = _build_valid_payload()
    payload["pages"] = payload["pages"][:1]

    with pytest.raises(ScriptJsonParseError) as exc_info:
        parse_script_response_from_llm(
            raw_output=_to_raw_json(payload),
            request=request,
        )

    assert exc_info.value.code == "SCRIPT_JSON_PAGE_COUNT_MISMATCH"


def test_page_index_mismatch_should_fail() -> None:
    """响应页码集合和请求页码集合不一致应失败。"""
    request = _build_request()
    payload = _build_valid_payload()
    payload["pages"][1]["page_index"] = 3

    with pytest.raises(ScriptJsonParseError) as exc_info:
        parse_script_response_from_llm(
            raw_output=_to_raw_json(payload),
            request=request,
        )

    assert exc_info.value.code == "SCRIPT_JSON_PAGE_INDEX_MISMATCH"


def test_duplicated_page_index_should_fail() -> None:
    """响应页码重复应失败。"""
    request = _build_request()
    payload = _build_valid_payload()
    payload["pages"][1]["page_index"] = 1

    with pytest.raises(ScriptJsonParseError) as exc_info:
        parse_script_response_from_llm(
            raw_output=_to_raw_json(payload),
            request=request,
        )

    assert exc_info.value.code == "SCRIPT_JSON_DUPLICATED_PAGE_INDEX"


def test_output_pages_should_be_sorted_by_page_index() -> None:
    """如果模型输出页顺序是乱序，但页码集合正确，应归一化为升序。"""
    request = _build_request()
    payload = _build_valid_payload()
    payload["pages"] = [
        payload["pages"][1],
        payload["pages"][0],
    ]

    result = parse_script_response_from_llm(
        raw_output=_to_raw_json(payload),
        request=request,
    )

    assert [page.page_index for page in result.pages] == [1, 2]


def test_non_json_output_should_fail() -> None:
    """非 JSON 文本应失败，并映射为 SCRIPT_JSON_PARSE_FAILED。"""
    request = _build_request()

    with pytest.raises(ScriptJsonParseError) as exc_info:
        parse_script_response_from_llm(
            raw_output="这是一个自然语言讲稿，不是 JSON。",
            request=request,
        )

    assert exc_info.value.code == "SCRIPT_JSON_PARSE_FAILED"
