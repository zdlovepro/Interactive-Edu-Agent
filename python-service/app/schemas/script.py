"""
讲稿生成相关的 Pydantic Schema 定义。

职责边界
========
1. 定义 Java 后端调用 Python 讲稿生成接口时的请求结构；
2. 定义大模型应输出的标准讲稿结构；
3. 定义 Python 内部可生成的 Java Callback Payload 结构；
4. 使用 Pydantic v2 做强类型约束，禁止额外字段，避免大模型输出污染业务结构。

注意
====
- 本文件只定义数据结构与字段级校验；
- 涉及“请求页码集合必须与响应页码集合一致”等跨对象业务校验，
  放在 app/services/script_json_parser.py 中完成；
- 涉及 “opening / transition / closing 如何转换成 Java scripts 节点”，
  放在 app/services/script_callback_adapter.py 中完成。
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# 基础模型配置
# ============================================================================

STRICT_MODEL_CONFIG = ConfigDict(
    # forbid 表示如果大模型输出了 schema 中不存在的字段，直接校验失败。
    # 这与 prompt 中“字段不得新增”的要求保持一致。
    extra="forbid",

    # 去除字符串首尾空白。
    # 注意：str_strip_whitespace 不会把空字符串变成 None；
    # 空字符串仍会由 min_length=1 拦截。
    str_strip_whitespace=True,

    # 允许通过字段名填充。
    populate_by_name=True,
)


# ============================================================================
# 请求模型
# ============================================================================

class PageContent(BaseModel):
    """
    单页课件内容。

    该结构由 Java 后端在课件解析完成后传入 Python。
    Python A 的讲稿生成任务基于这些文本内容生成自然口语化讲稿。

    Attributes
    ----------
    page_index:
        页码，从 1 开始。
    title:
        本页标题，可为空。
    text_content:
        本页提取出的正文文本。
    keywords:
        本页关键词列表，可为空。
    """

    model_config = STRICT_MODEL_CONFIG

    page_index: int = Field(
        ...,
        ge=1,
        description="页码，从 1 开始",
        examples=[1],
    )
    title: Optional[str] = Field(
        default=None,
        description="本页标题，可为空",
        examples=["递归简介"],
    )
    text_content: str = Field(
        ...,
        min_length=1,
        description="本页提取的正文文本，不允许为空",
        examples=["递归是函数直接或间接调用自身的编程技术，需要有终止条件。"],
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="本页关键词列表",
        examples=[["递归", "终止条件", "函数调用"]],
    )


class ScriptGenerateRequest(BaseModel):
    """
    讲稿生成请求。

    由 Java 后端调用 Python 内部接口 /python/v1/script/generate 时传入。
    """

    model_config = STRICT_MODEL_CONFIG

    courseware_id: str = Field(
        ...,
        min_length=1,
        description="课件唯一标识",
        examples=["cware_123456"],
    )
    courseware_name: str = Field(
        ...,
        min_length=1,
        description="课件名称，用于生成开场白",
        examples=["数据结构导论"],
    )
    subject: Optional[str] = Field(
        default=None,
        description="课件学科/方向，辅助生成风格，例如：数据结构、高等数学",
        examples=["计算机科学"],
    )
    pages: List[PageContent] = Field(
        ...,
        min_length=1,
        description="各页内容列表，按页码升序排列",
    )


# ============================================================================
# 大模型输出模型
# ============================================================================

class PageScript(BaseModel):
    """
    单页讲稿。

    这是大模型输出 JSON 中 pages 数组的元素结构。
    """

    model_config = STRICT_MODEL_CONFIG

    page_index: int = Field(
        ...,
        ge=1,
        description="对应页码，从 1 开始",
        examples=[1],
    )
    script: str = Field(
        ...,
        min_length=1,
        description="该页的核心口语化讲解内容，不允许为空",
        examples=["首先我们来看递归的基本概念。递归，简单来说就是一个函数在执行过程中调用自身。"],
    )
    transition: str = Field(
        ...,
        min_length=1,
        description="过渡到下一页的衔接语；最后一页为本页小结语，不允许为空",
        examples=["了解了递归的定义之后，接下来我们看一个经典应用。"],
    )


class ScriptGenerateResponse(BaseModel):
    """
    讲稿生成结果。

    这是大模型输出经过 JSON 解析和 Pydantic 强校验后的标准结构。
    """

    model_config = STRICT_MODEL_CONFIG

    courseware_id: str = Field(
        ...,
        min_length=1,
        description="课件唯一标识，必须与请求中的 courseware_id 一致",
        examples=["cware_123456"],
    )
    opening: str = Field(
        ...,
        min_length=1,
        description="整节课的开场白，不允许为空",
        examples=["大家好，欢迎来到《数据结构导论》的学习！"],
    )
    pages: List[PageScript] = Field(
        ...,
        min_length=1,
        description="各页讲稿列表，与请求页码一一对应",
    )
    closing: str = Field(
        ...,
        min_length=1,
        description="整节课的结语，不允许为空",
        examples=["本节课我们掌握了递归的定义、终止条件和典型应用。"],
    )


class ScriptGenerateResult(BaseModel):
    """
    对外统一响应包装。

    路由层 response_model 使用该结构。
    """

    model_config = STRICT_MODEL_CONFIG

    code: int = Field(
        default=0,
        description="0 表示成功，非 0 表示失败",
        examples=[0],
    )
    message: str = Field(
        default="success",
        description="结果描述",
        examples=["success"],
    )
    data: Optional[ScriptGenerateResponse] = Field(
        default=None,
        description="讲稿数据，失败时为 null",
    )


# ============================================================================
# Java Callback Payload 模型
# ============================================================================

class ScriptCallbackNode(BaseModel):
    """
    Java 回调结构中的单个讲稿节点。

    对应 Java:
    ScriptCallbackRequest.ScriptNodeDto
    """

    model_config = STRICT_MODEL_CONFIG

    nodeId: str = Field(
        ...,
        min_length=1,
        description="唯一节点标识，例如 n_1_main",
        examples=["n_1_main"],
    )
    content: str = Field(
        ...,
        min_length=1,
        description="讲稿节点内容，不允许为空",
        examples=["首先我们来看递归的基本概念。"],
    )


class ScriptCallbackPage(BaseModel):
    """
    Java 回调结构中的单页讲稿。

    对应 Java:
    ScriptCallbackRequest.PageScriptDto
    """

    model_config = STRICT_MODEL_CONFIG

    pageIndex: int = Field(
        ...,
        ge=1,
        description="页码，从 1 开始",
        examples=[1],
    )
    originalText: str = Field(
        default="",
        description="这一页的原始文本内容",
        examples=["递归是函数直接或间接调用自身的编程技术。"],
    )
    scripts: List[ScriptCallbackNode] = Field(
        default_factory=list,
        description="讲稿切割后的节点列表",
    )


class ScriptCallbackPayload(BaseModel):
    """
    Python 发送给 Java 后端 /api/v1/courseware/callback 的 payload 结构。

    对应 Java:
    ScriptCallbackRequest
    """

    model_config = STRICT_MODEL_CONFIG

    coursewareId: str = Field(
        ...,
        min_length=1,
        description="课件唯一标识",
        examples=["cware_123456"],
    )
    processStatus: str = Field(
        ...,
        min_length=1,
        description="Python 处理状态：SUCCESS / FAILED",
        examples=["SUCCESS"],
    )
    errorMessage: Optional[str] = Field(
        default=None,
        description="如果处理失败，可携带错误信息",
        examples=[None],
    )
    pages: List[ScriptCallbackPage] = Field(
        default_factory=list,
        description="课件各页生成的讲稿内容列表",
    )
