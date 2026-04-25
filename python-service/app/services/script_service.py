"""
讲稿生成服务 —— Prompt 工程与业务编排模块。
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

from app.clients.llm_client import get_llm_client
from app.schemas.script import ScriptGenerateRequest
from app.services.script_callback_adapter import (
    build_success_callback_payload,
    callback_payload_to_dict,
)
from app.services.script_json_parser import (
    ScriptJsonParseError,
    parse_script_response_from_llm,
)

logger = logging.getLogger(__name__)

_SYSTEM_TEMPLATE = """\
你是一位经验丰富的教育领域 AI 讲师助手，擅长将课件内容转化为自然流畅、生动易懂的口语化讲稿。
生成的讲稿将直接用于 AI 数字人朗读，须满足以下要求：

【角色与风格】
- 语气亲切、专业，贴近真实课堂授课风格；
- 避免书面化长句，优先使用短句、举例、类比；
- 重点知识点需着重强调，帮助学生理解和记忆。

【结构要求】
- 开场白 opening：热情介绍课件主题与本节学习目标，约 100-150 字；
- 每页讲解 pages[].script：聚焦本页核心知识点，配合说明与举例，约 150-300 字；
- 过渡语 pages[].transition：自然衔接当前页与下一页，起承上启下作用，约 30-50 字；
  最后一页的 transition 为本页内容的小结语，约 30-50 字；
- 结语 closing：总结本节重点，鼓励学生，约 50-80 字。

【输出约束 —— 极其重要】
- 必须且只能输出一个合法 JSON object；
- 不得包含任何 Markdown 代码块标记，例如 ```json 或 ```；
- 不得包含注释；
- 不得包含解释性文字；
- 不得输出多个 JSON；
- 不得输出数组作为顶层结构；
- 字段不得缺失；
- 字段不得新增；
- 字符串字段不得为空；
- page_index 必须与输入页码一致；
- courseware_id 必须与输入课件 ID 一致；
- 字符串值中如果包含英文双引号，必须正确转义。
"""

_JSON_SCHEMA_EXAMPLE = """\
{
  "courseware_id": "<与请求中一致的课件ID，字符串>",
  "opening": "<整节课开场白，字符串，不允许为空>",
  "pages": [
    {
      "page_index": 1,
      "script": "<第1页讲解内容，字符串，不允许为空>",
      "transition": "<过渡到第2页的衔接语，字符串，不允许为空>"
    },
    {
      "page_index": 2,
      "script": "<第2页讲解内容，字符串，不允许为空>",
      "transition": "<最后一页小结语，字符串，不允许为空>"
    }
  ],
  "closing": "<整节课结语，字符串，不允许为空>"
}"""

_HUMAN_TEMPLATE = """\
请根据以下课件信息生成完整结构化讲稿。

【课件信息】
课件 ID：{courseware_id}
课件名称：{courseware_name}
学科方向：{subject}
总页数：{total_pages}
必须输出的页码列表：{page_indexes}

【各页内容】
{pages_content}

【必须严格遵守的 JSON 结构示例】
{json_schema}

【再次强调】
你只能输出一个 JSON object。
不要输出 Markdown。
不要输出解释文字。
不要输出“以下是 JSON”等前缀。
不要省略任何页。
不要增加任何字段。

现在请直接输出 JSON object：
"""


def _build_prompt_template() -> ChatPromptTemplate:
    """构建 ChatPromptTemplate。"""
    return ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(_SYSTEM_TEMPLATE),
            HumanMessagePromptTemplate.from_template(_HUMAN_TEMPLATE),
        ]
    )


_PROMPT_TEMPLATE = _build_prompt_template()


def _format_pages_content(request: ScriptGenerateRequest) -> str:
    """将各页内容序列化为简洁文本块，便于 Prompt 理解。"""
    lines: list[str] = []

    for page in request.pages:
        lines.append(f"--- 第 {page.page_index} 页 ---")

        if page.title:
            lines.append(f"标题：{page.title}")

        lines.append(f"正文：{page.text_content.strip()}")

        if page.keywords:
            lines.append(f"关键词：{'、'.join(page.keywords)}")

        lines.append("")

    return "\n".join(lines).strip()


def _get_page_indexes(request: ScriptGenerateRequest) -> str:
    """返回请求中的页码列表字符串。"""
    indexes = [page.page_index for page in request.pages]
    return str(indexes)


def generate_script(request: ScriptGenerateRequest) -> Dict[str, Any]:
    """
    生成结构化讲稿的核心服务函数。

    当前函数仍保持同步返回 ScriptGenerateResponse。
    为任务 6 预留了 callback payload 的构造日志，但不在本函数中主动回调 Java。
    """

    logger.info(
        "开始生成讲稿 | courseware_id=%s | pages=%d",
        request.courseware_id,
        len(request.pages),
    )

    prompt_messages = _build_prompt_messages(request)

    try:
        raw_output = _invoke_llm(prompt_messages=prompt_messages, request=request)
    except Exception as exc:
        logger.error(
            "大模型调用异常 | courseware_id=%s | error_type=%s | error=%s",
            request.courseware_id,
            type(exc).__name__,
            exc,
        )
        return {
            "code": 50202,
            "message": f"大模型服务异常：{type(exc).__name__}",
            "data": None,
        }

    try:
        result = parse_script_response_from_llm(
            raw_output=raw_output,
            request=request,
        )
    except ScriptJsonParseError as exc:
        logger.error(
            "讲稿 JSON 解析或校验失败 | courseware_id=%s | error_code=%s | error=%s | raw_preview=%s",
            request.courseware_id,
            exc.code,
            exc,
            _safe_preview(raw_output),
        )
        return {
            "code": 50202,
            "message": exc.message,
            "data": None,
        }
    except Exception as exc:
        logger.exception(
            "讲稿解析发生未预期异常 | courseware_id=%s | error_type=%s",
            request.courseware_id,
            type(exc).__name__,
        )
        return {
            "code": 50001,
            "message": "Python 服务内部错误：讲稿解析失败",
            "data": None,
        }

    try:
        callback_payload = build_success_callback_payload(
            request=request,
            script=result,
        )
        callback_payload_dict = callback_payload_to_dict(callback_payload)
        logger.info(
            "讲稿 Java callback payload 构造成功 | courseware_id=%s | pages=%d",
            request.courseware_id,
            len(callback_payload_dict.get("pages", [])),
        )
    except Exception as exc:
        logger.exception(
            "讲稿 Java callback payload 构造失败 | courseware_id=%s | error_type=%s",
            request.courseware_id,
            type(exc).__name__,
        )

    logger.info(
        "讲稿生成成功 | courseware_id=%s | pages=%d",
        request.courseware_id,
        len(result.pages),
    )

    return {
        "code": 0,
        "message": "success",
        "data": result.model_dump(mode="json"),
    }


def _build_prompt_messages(request: ScriptGenerateRequest):
    """构造发送给 LLM 的 prompt messages。"""
    pages_content = _format_pages_content(request)
    subject_str = request.subject or "通用课程"

    return _PROMPT_TEMPLATE.format_messages(
        courseware_id=request.courseware_id,
        courseware_name=request.courseware_name,
        subject=subject_str,
        total_pages=len(request.pages),
        page_indexes=_get_page_indexes(request),
        pages_content=pages_content,
        json_schema=_JSON_SCHEMA_EXAMPLE,
    )


def _invoke_llm(prompt_messages, request: ScriptGenerateRequest) -> str:
    """调用大模型并返回原始文本。"""
    logger.info(
        "调用大模型生成讲稿 | courseware_id=%s | message_count=%d",
        request.courseware_id,
        len(prompt_messages),
    )

    llm_client = get_llm_client()
    raw_output = llm_client.invoke(prompt_messages)

    logger.info(
        "大模型返回讲稿原始内容 | courseware_id=%s | output_length=%d",
        request.courseware_id,
        len(raw_output or ""),
    )

    return raw_output or ""


def _safe_preview(raw_output: str, limit: int = 300) -> str:
    """返回模型原始输出的安全预览，用于日志排查。"""
    if raw_output is None:
        return "<None>"

    normalized = raw_output.replace("\r", "\\r").replace("\n", "\\n")
    if len(normalized) <= limit:
        return normalized

    return normalized[:limit] + "...<truncated>"
