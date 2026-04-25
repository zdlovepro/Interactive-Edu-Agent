"""
LLM JSON 解析工具。

职责
====
本模块负责把大模型返回的“不稳定文本”解析为 Python dict。

大模型常见输出问题包括：
1. 明明要求输出 JSON，却包裹了 ```json ... ```；
2. JSON 前后带了解释性文字；
3. 输出为空；
4. 输出顶层不是 object；
5. 多了尾逗号；
6. 包含不可见控制字符；
7. JSON 语法错误。

本模块只负责“通用 JSON 提取与解析”，不负责讲稿业务规则。
讲稿业务规则放在 app/services/script_json_parser.py 中。

设计原则
========
- 不直接吞掉异常；
- 不返回半可信数据；
- 所有失败都抛出明确的 LLMJsonError 子类；
- 默认只接受 JSON object，不接受顶层数组；
- 不把原始模型输出暴露给调用方，只允许上层日志做截断记录。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional


# ============================================================================
# 异常定义
# ============================================================================

@dataclass
class LLMJsonError(Exception):
    """
    LLM JSON 解析异常基类。

    Attributes
    ----------
    reason:
        面向日志和内部定位的错误原因。
    detail:
        可选详细信息，避免直接暴露完整模型输出。
    """

    reason: str
    detail: Optional[str] = None

    def __str__(self) -> str:
        if self.detail:
            return f"{self.reason}: {self.detail}"
        return self.reason


class LLMJsonEmptyOutputError(LLMJsonError):
    """模型输出为空。"""


class LLMJsonExtractError(LLMJsonError):
    """无法从模型输出中提取 JSON object。"""


class LLMJsonDecodeError(LLMJsonError):
    """JSON 语法解析失败。"""


class LLMJsonTopLevelTypeError(LLMJsonError):
    """JSON 顶层类型不符合要求。"""


# ============================================================================
# 正则与常量
# ============================================================================

_MARKDOWN_JSON_FENCE_PATTERN = re.compile(
    r"^\s*```(?:json|JSON)?\s*(?P<body>[\s\S]*?)\s*```\s*$",
    re.IGNORECASE,
)

_CONTROL_CHAR_PATTERN = re.compile(
    # JSON 标准不允许除 \t \n \r 之外的裸控制字符。
    # 这里删除 0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F。
    r"[\x00-\x08\x0B\x0C\x0E-\x1F]"
)

_TRAILING_COMMA_PATTERN = re.compile(
    # 移除对象或数组结束前的尾逗号：
    # {"a": 1,} -> {"a": 1}
    # [1,2,] -> [1,2]
    r",(\s*[}\]])"
)


# ============================================================================
# 对外主函数
# ============================================================================

def parse_llm_json_object(raw_output: str) -> Dict[str, Any]:
    """
    将大模型原始输出解析为 JSON object。

    Parameters
    ----------
    raw_output:
        大模型返回的原始文本。

    Returns
    -------
    Dict[str, Any]
        解析后的 JSON object。

    Raises
    ------
    LLMJsonEmptyOutputError
        raw_output 为空或仅包含空白字符。
    LLMJsonExtractError
        无法从文本中提取 JSON object。
    LLMJsonDecodeError
        提取到的文本不是合法 JSON。
    LLMJsonTopLevelTypeError
        JSON 顶层不是 object。
    """

    if raw_output is None:
        raise LLMJsonEmptyOutputError(reason="LLM output is None")

    normalized = _normalize_text(raw_output)
    if not normalized:
        raise LLMJsonEmptyOutputError(reason="LLM output is empty")

    stripped = normalized.strip()

    if stripped.startswith("["):
        raise LLMJsonExtractError(
            reason="LLM JSON top level must be object, not array"
        )

    json_text = extract_json_object_text(normalized)
    repaired = repair_json_text(json_text)

    try:
        data = json.loads(repaired)
    except json.JSONDecodeError as exc:
        raise LLMJsonDecodeError(
            reason="Failed to decode JSON",
            detail=f"line={exc.lineno}, column={exc.colno}, message={exc.msg}",
        ) from exc

    if not isinstance(data, dict):
        raise LLMJsonTopLevelTypeError(
            reason="Top-level JSON value must be an object",
            detail=f"actual_type={type(data).__name__}",
        )

    return data


# ============================================================================
# JSON 文本提取
# ============================================================================

def extract_json_object_text(text: str) -> str:
    """
    从文本中提取 JSON object 字符串。

    支持以下形式：
    1. 纯 JSON object：
       {"a": 1}

    2. Markdown fence：
       ```json
       {"a": 1}
       ```

    3. 前后带解释文本：
       以下是 JSON：
       {"a": 1}
       请查收。

    注意
    ----
    本函数只提取顶层 object，即必须找到成对的最外层 `{...}`。
    如果模型输出顶层数组，本任务视为错误。
    """

    stripped = text.strip()

    # 先处理整体被 markdown fence 包住的情况。
    fence_match = _MARKDOWN_JSON_FENCE_PATTERN.match(stripped)
    if fence_match:
        stripped = fence_match.group("body").strip()

    start_index = stripped.find("{")
    if start_index < 0:
        raise LLMJsonExtractError(reason="No JSON object start brace found")

    end_index = _find_matching_closing_brace(stripped, start_index)
    if end_index < 0:
        raise LLMJsonExtractError(reason="No matching closing brace found")

    return stripped[start_index:end_index + 1].strip()


def _find_matching_closing_brace(text: str, start_index: int) -> int:
    """
    从 start_index 指向的 `{` 开始，寻找匹配的 `}`。

    该实现会正确跳过字符串内部的大括号，例如：
    {"text": "这里有一个 { 不是结构括号"}

    Parameters
    ----------
    text:
        输入文本。
    start_index:
        第一个 `{` 的位置。

    Returns
    -------
    int
        匹配到的 `}` 的位置；如果未匹配，返回 -1。
    """

    depth = 0
    in_string = False
    escape = False

    for index in range(start_index, len(text)):
        char = text[index]

        if in_string:
            if escape:
                escape = False
                continue

            if char == "\\":
                escape = True
                continue

            if char == '"':
                in_string = False
                continue

            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1
            continue

        if char == "}":
            depth -= 1
            if depth == 0:
                return index

    return -1


# ============================================================================
# JSON 文本修复
# ============================================================================

def repair_json_text(json_text: str) -> str:
    """
    对提取到的 JSON 文本做轻量修复。

    当前修复范围
    ============
    1. 去除 BOM；
    2. 去除不可见控制字符；
    3. 替换中文引号为英文引号；
    4. 移除对象或数组结束前的尾逗号。

    明确不处理
    ==========
    1. 单引号 JSON；
    2. key 未加引号；
    3. 严重截断 JSON；
    4. 混乱嵌套结构。

    原因
    ====
    这些修复很容易误改内容。若后续团队允许增加依赖，
    可以考虑引入 json-repair，但即使引入，也必须再次通过 Pydantic 强校验。
    """

    repaired = json_text.strip()

    # 去除 UTF-8 BOM。
    repaired = repaired.lstrip("\ufeff")

    # 删除不允许出现在 JSON 中的裸控制字符。
    repaired = _CONTROL_CHAR_PATTERN.sub("", repaired)

    # 替换常见中文引号。
    repaired = repaired.replace("“", '"').replace("”", '"')
    repaired = repaired.replace("‘", "'").replace("’", "'")

    # 移除尾逗号。
    previous = None
    while previous != repaired:
        previous = repaired
        repaired = _TRAILING_COMMA_PATTERN.sub(r"\1", repaired)

    return repaired


# ============================================================================
# 文本标准化
# ============================================================================

def _normalize_text(text: str) -> str:
    """
    统一大模型输出文本的基础格式。

    注意
    ----
    本函数不会做业务修复，只做安全的格式标准化。
    """

    return text.strip()
