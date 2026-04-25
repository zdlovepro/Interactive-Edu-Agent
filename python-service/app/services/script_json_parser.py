"""
讲稿 JSON 解析与业务校验模块。

职责
====
本模块负责将大模型原始输出解析为 ScriptGenerateResponse，并进行业务一致性校验。

处理流程
========
raw_output
    -> app.utils.llm_json.parse_llm_json_object
    -> ScriptGenerateResponse.model_validate
    -> courseware_id 一致性校验
    -> 页码集合一致性校验
    -> 页码重复校验
    -> 输出顺序归一化
    -> 返回 ScriptGenerateResponse

为什么不把这些逻辑放在 script_service.py？
======================================
script_service.py 应只负责编排：
- 构造 prompt；
- 调用 LLM；
- 调用本模块；
- 组织统一响应。

这样可以让 JSON 解析与校验逻辑可复用、可测试，也符合项目 Python 服务开发规约。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from pydantic import ValidationError

from app.schemas.script import (
    PageScript,
    ScriptGenerateRequest,
    ScriptGenerateResponse,
)
from app.utils.llm_json import (
    LLMJsonError,
    parse_llm_json_object,
)


# ============================================================================
# 异常定义
# ============================================================================

@dataclass
class ScriptJsonParseError(Exception):
    """
    讲稿 JSON 解析与校验异常。

    Attributes
    ----------
    code:
        内部错误码，用于日志和测试定位。
    message:
        对上层 service 可见的错误描述。
    detail:
        可选详细信息，不应直接暴露给前端或外部调用方。
    """

    code: str
    message: str
    detail: Optional[str] = None

    def __str__(self) -> str:
        if self.detail:
            return f"{self.code}: {self.message} | {self.detail}"
        return f"{self.code}: {self.message}"


# ============================================================================
# 对外主函数
# ============================================================================

def parse_script_response_from_llm(
    raw_output: str,
    request: ScriptGenerateRequest,
) -> ScriptGenerateResponse:
    """
    将 LLM 原始输出解析并校验为 ScriptGenerateResponse。

    Parameters
    ----------
    raw_output:
        LLM 返回的原始文本。
    request:
        本次讲稿生成请求。用于校验 courseware_id、页码、页数等业务一致性。

    Returns
    -------
    ScriptGenerateResponse
        通过 JSON 解析、Pydantic 校验和业务校验的稳定讲稿结构。

    Raises
    ------
    ScriptJsonParseError
        任意 JSON 提取、解析、字段校验、业务校验失败时抛出。
    """

    try:
        data = parse_llm_json_object(raw_output)
    except LLMJsonError as exc:
        raise ScriptJsonParseError(
            code="SCRIPT_JSON_PARSE_FAILED",
            message="大模型输出格式异常：JSON 解析失败",
            detail=str(exc),
        ) from exc

    # 如果模型没有返回 courseware_id，可以用请求中的 courseware_id 补齐。
    # 如果模型返回了 courseware_id 但与请求不一致，应判定失败，而不是静默覆盖。
    if "courseware_id" not in data:
        data["courseware_id"] = request.courseware_id

    try:
        response = ScriptGenerateResponse.model_validate(data)
    except ValidationError as exc:
        raise ScriptJsonParseError(
            code="SCRIPT_JSON_SCHEMA_INVALID",
            message="大模型输出格式异常：字段校验失败",
            detail=str(exc),
        ) from exc

    _validate_courseware_id(response=response, request=request)
    _validate_pages(response=response, request=request)

    # 按 page_index 归一化排序，保证后续回调、TTS、播放顺序稳定。
    sorted_pages = sorted(response.pages, key=lambda page: page.page_index)
    normalized = response.model_copy(update={"pages": sorted_pages})

    return normalized


# ============================================================================
# 业务校验
# ============================================================================

def _validate_courseware_id(
    response: ScriptGenerateResponse,
    request: ScriptGenerateRequest,
) -> None:
    """
    校验响应中的 courseware_id 与请求一致。
    """

    if response.courseware_id != request.courseware_id:
        raise ScriptJsonParseError(
            code="SCRIPT_JSON_COURSEWARE_ID_MISMATCH",
            message="大模型输出内容与请求课件ID不一致",
            detail=(
                f"expected={request.courseware_id}, "
                f"actual={response.courseware_id}"
            ),
        )


def _validate_pages(
    response: ScriptGenerateResponse,
    request: ScriptGenerateRequest,
) -> None:
    """
    校验讲稿页码与请求页码完全一致。

    校验项
    ======
    1. 响应 pages 不能为空；
    2. 响应 page_index 不允许重复；
    3. 响应 page_index 集合必须与请求 page_index 集合一致；
    4. 响应 pages 数量必须与请求 pages 数量一致。
    """

    request_page_indexes = [page.page_index for page in request.pages]
    response_page_indexes = [page.page_index for page in response.pages]

    if not response_page_indexes:
        raise ScriptJsonParseError(
            code="SCRIPT_JSON_EMPTY_PAGES",
            message="大模型输出格式异常：讲稿页列表为空",
        )

    duplicated_indexes = _find_duplicates(response_page_indexes)
    if duplicated_indexes:
        raise ScriptJsonParseError(
            code="SCRIPT_JSON_DUPLICATED_PAGE_INDEX",
            message="大模型输出格式异常：讲稿页码重复",
            detail=f"duplicated_page_indexes={duplicated_indexes}",
        )

    request_set = set(request_page_indexes)
    response_set = set(response_page_indexes)

    if len(response_page_indexes) != len(request_page_indexes):
        raise ScriptJsonParseError(
            code="SCRIPT_JSON_PAGE_COUNT_MISMATCH",
            message="大模型输出内容与课件页数不一致",
            detail=(
                f"expected_count={len(request_page_indexes)}, "
                f"actual_count={len(response_page_indexes)}"
            ),
        )

    if request_set != response_set:
        missing = sorted(request_set - response_set)
        unexpected = sorted(response_set - request_set)
        raise ScriptJsonParseError(
            code="SCRIPT_JSON_PAGE_INDEX_MISMATCH",
            message="大模型输出内容与课件页码不一致",
            detail=f"missing={missing}, unexpected={unexpected}",
        )

    # 额外防御：检查每页 script / transition 非空。
    # 这通常已经由 Pydantic min_length 拦截，这里保留是为了表达业务语义。
    for page in response.pages:
        _validate_page_text(page)


def _validate_page_text(page: PageScript) -> None:
    """
    校验单页讲稿文本内容。
    """

    if not page.script.strip():
        raise ScriptJsonParseError(
            code="SCRIPT_JSON_EMPTY_PAGE_SCRIPT",
            message="大模型输出格式异常：页面讲稿为空",
            detail=f"page_index={page.page_index}",
        )

    if not page.transition.strip():
        raise ScriptJsonParseError(
            code="SCRIPT_JSON_EMPTY_PAGE_TRANSITION",
            message="大模型输出格式异常：页面过渡语为空",
            detail=f"page_index={page.page_index}",
        )


def _find_duplicates(values: List[int]) -> List[int]:
    """
    返回列表中重复出现的整数，按升序去重。
    """

    seen = set()
    duplicated = set()

    for value in values:
        if value in seen:
            duplicated.add(value)
        else:
            seen.add(value)

    return sorted(duplicated)
