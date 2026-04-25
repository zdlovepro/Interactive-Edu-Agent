"""
LLM JSON 通用解析器测试。

测试目标
========
验证 app.utils.llm_json.parse_llm_json_object 是否能稳定处理大模型常见输出：

1. 标准 JSON object；
2. Markdown fenced JSON；
3. JSON 前后带解释文本；
4. 尾逗号；
5. 中文引号；
6. 空输出；
7. 非 JSON 文本；
8. 顶层数组；
9. 缺失右大括号；
10. 字符串内部包含大括号。

这些测试不涉及讲稿业务，只验证通用 JSON 提取与解析能力。
"""

from __future__ import annotations

import pytest

from app.utils.llm_json import (
    LLMJsonDecodeError,
    LLMJsonEmptyOutputError,
    LLMJsonExtractError,
    extract_json_object_text,
    parse_llm_json_object,
    repair_json_text,
)


def test_parse_standard_json_object_success() -> None:
    """标准 JSON object 应解析成功。"""
    raw_output = '{"name": "递归", "page": 1}'

    result = parse_llm_json_object(raw_output)

    assert result == {
        "name": "递归",
        "page": 1,
    }


def test_parse_markdown_fenced_json_success() -> None:
    """被 ```json ... ``` 包裹的 JSON 应解析成功。"""
    raw_output = """
```json
{
  "name": "递归",
  "page": 1
}
```
"""

    result = parse_llm_json_object(raw_output)

    assert result["name"] == "递归"
    assert result["page"] == 1


def test_parse_json_with_prefix_and_suffix_text_success() -> None:
    """JSON 前后带解释文本时，应提取最外层 JSON object。"""
    raw_output = """
下面是生成结果：
{
  "name": "递归",
  "page": 1
}
以上内容请查收。
"""

    result = parse_llm_json_object(raw_output)

    assert result == {
        "name": "递归",
        "page": 1,
    }


def test_parse_json_with_trailing_comma_success() -> None:
    """对象或数组末尾多余逗号应被轻量修复。"""
    raw_output = """
{
  "name": "递归",
  "items": ["定义", "终止条件",],
}
"""

    result = parse_llm_json_object(raw_output)

    assert result["name"] == "递归"
    assert result["items"] == ["定义", "终止条件"]


def test_repair_json_text_replace_chinese_double_quotes() -> None:
    """中文双引号应被替换为英文双引号。"""
    raw_text = '“name”: “递归”'

    repaired = repair_json_text(raw_text)

    assert repaired == '"name": "递归"'


def test_parse_json_with_chinese_quotes_success() -> None:
    """使用中文双引号包裹 key/value 的简单 JSON 应可修复。"""
    raw_output = """
{
  “name”: “递归”,
  “page”: 1
}
"""

    result = parse_llm_json_object(raw_output)

    assert result["name"] == "递归"
    assert result["page"] == 1


def test_empty_string_should_fail() -> None:
    """空字符串应抛出 LLMJsonEmptyOutputError。"""
    with pytest.raises(LLMJsonEmptyOutputError):
        parse_llm_json_object("")


def test_blank_string_should_fail() -> None:
    """仅包含空白字符的字符串应抛出 LLMJsonEmptyOutputError。"""
    with pytest.raises(LLMJsonEmptyOutputError):
        parse_llm_json_object("   \n\t   ")


def test_none_output_should_fail() -> None:
    """None 输出应抛出 LLMJsonEmptyOutputError。"""
    with pytest.raises(LLMJsonEmptyOutputError):
        parse_llm_json_object(None)  # type: ignore[arg-type]


def test_non_json_text_should_fail() -> None:
    """完全不含 JSON object 的自然语言文本应抛出 LLMJsonExtractError。"""
    with pytest.raises(LLMJsonExtractError):
        parse_llm_json_object("这是一个讲稿，但不是 JSON。")


def test_top_level_array_should_fail() -> None:
    """顶层数组不符合本任务要求，应失败。"""
    with pytest.raises(LLMJsonExtractError):
        parse_llm_json_object('[{"name": "递归"}]')


def test_missing_closing_brace_should_fail() -> None:
    """缺失右大括号，应提取失败。"""
    with pytest.raises(LLMJsonExtractError):
        parse_llm_json_object('{"name": "递归"')


def test_invalid_json_syntax_should_fail_with_decode_error() -> None:
    """能提取到大括号块，但 JSON 语法错误时，应抛出 LLMJsonDecodeError。"""
    raw_output = """
{
  "name": "递归",
  "page":
}
"""

    with pytest.raises(LLMJsonDecodeError):
        parse_llm_json_object(raw_output)


def test_extract_json_with_braces_inside_string_success() -> None:
    """字符串内部包含大括号时，不应干扰最外层大括号匹配。"""
    raw_output = """
解释文本
{
  "content": "这里有一个 { 符号，但它在字符串里",
  "page": 1
}
后续文本
"""

    json_text = extract_json_object_text(raw_output)

    assert '"content"' in json_text
    assert '"page": 1' in json_text

    result = parse_llm_json_object(raw_output)

    assert result["content"] == "这里有一个 { 符号，但它在字符串里"
    assert result["page"] == 1


def test_nested_object_success() -> None:
    """嵌套 object 应解析成功。"""
    raw_output = """
{
  "outer": {
    "inner": {
      "name": "递归"
    }
  }
}
"""

    result = parse_llm_json_object(raw_output)

    assert result["outer"]["inner"]["name"] == "递归"


def test_multiple_json_objects_extract_first_complete_object() -> None:
    """
    如果文本中出现多个 JSON object，当前策略提取第一个完整 object。

    正常 Prompt 已要求不得输出多个 JSON。
    该测试只是锁定当前提取策略，避免贪婪正则误吞多个对象。
    """
    raw_output = """
{"first": true}
{"second": true}
"""

    result = parse_llm_json_object(raw_output)

    assert result == {"first": True}
