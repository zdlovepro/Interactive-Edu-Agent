"""
讲稿 Java Callback Payload 适配器。

职责
====
将 Python A 生成并校验后的 ScriptGenerateResponse 转换为 Java 后端
ScriptCallbackRequest 所需的结构。

Java 后端期望结构
================
{
  "coursewareId": "...",
  "processStatus": "SUCCESS",
  "errorMessage": null,
  "pages": [
    {
      "pageIndex": 1,
      "originalText": "...",
      "scripts": [
        {
          "nodeId": "n_1_main",
          "content": "..."
        }
      ]
    }
  ]
}

设计说明
========
1. Python 内部讲稿结构保留 opening / page script / transition / closing，
   因为这更适合大模型生成；
2. Java 落库结构使用 page scripts nodes，
   因为这更适合后续 TTS、播放状态机、断点恢复；
3. 本模块是二者之间的显式转换层，避免两个结构互相污染。
"""

from __future__ import annotations

from typing import Dict, List

from app.schemas.script import (
    PageContent,
    ScriptCallbackNode,
    ScriptCallbackPage,
    ScriptCallbackPayload,
    ScriptGenerateRequest,
    ScriptGenerateResponse,
)


def build_success_callback_payload(
    request: ScriptGenerateRequest,
    script: ScriptGenerateResponse,
) -> ScriptCallbackPayload:
    """
    构建 Java 成功回调 Payload。

    Parameters
    ----------
    request:
        原始讲稿生成请求。用于获取每页 originalText。
    script:
        已通过强校验的讲稿生成结果。

    Returns
    -------
    ScriptCallbackPayload
        可直接序列化并发送给 Java /api/v1/courseware/callback 的结构。
    """

    page_content_map = _build_page_content_map(request.pages)
    total_pages = len(script.pages)

    callback_pages: List[ScriptCallbackPage] = []

    for page_script in script.pages:
        page_index = page_script.page_index
        source_page = page_content_map[page_index]

        nodes: List[ScriptCallbackNode] = []

        # opening 放在第一页第一个节点。
        if page_index == 1:
            nodes.append(
                ScriptCallbackNode(
                    nodeId=_build_node_id(page_index=page_index, kind="opening"),
                    content=script.opening,
                )
            )

        # 每页主讲稿节点。
        nodes.append(
            ScriptCallbackNode(
                nodeId=_build_node_id(page_index=page_index, kind="main"),
                content=page_script.script,
            )
        )

        # 每页过渡语节点。
        nodes.append(
            ScriptCallbackNode(
                nodeId=_build_node_id(page_index=page_index, kind="transition"),
                content=page_script.transition,
            )
        )

        # closing 放在最后一页最后一个节点。
        if page_index == total_pages:
            nodes.append(
                ScriptCallbackNode(
                    nodeId=_build_node_id(page_index=page_index, kind="closing"),
                    content=script.closing,
                )
            )

        callback_pages.append(
            ScriptCallbackPage(
                pageIndex=page_index,
                originalText=source_page.text_content,
                scripts=nodes,
            )
        )

    return ScriptCallbackPayload(
        coursewareId=request.courseware_id,
        processStatus="SUCCESS",
        errorMessage=None,
        pages=callback_pages,
    )


def build_failed_callback_payload(
    courseware_id: str,
    error_message: str,
) -> ScriptCallbackPayload:
    """
    构建 Java 失败回调 Payload。

    Parameters
    ----------
    courseware_id:
        课件 ID。
    error_message:
        失败原因。应为脱敏后的简短错误说明，不应包含完整大模型原始输出。

    Returns
    -------
    ScriptCallbackPayload
        失败回调结构。
    """

    return ScriptCallbackPayload(
        coursewareId=courseware_id,
        processStatus="FAILED",
        errorMessage=error_message,
        pages=[],
    )


def callback_payload_to_dict(payload: ScriptCallbackPayload) -> Dict:
    """
    将 ScriptCallbackPayload 转为 dict。

    说明
    ====
    Java 侧字段使用 camelCase：
    - coursewareId
    - processStatus
    - errorMessage
    - pageIndex
    - originalText
    - nodeId

    因此这里直接使用 by_alias=False 即可，因为模型字段本身就是 camelCase。
    """

    return payload.model_dump(mode="json", by_alias=False)


def _build_page_content_map(pages: List[PageContent]) -> Dict[int, PageContent]:
    """
    构建 page_index -> PageContent 的映射。

    注意
    ----
    页码一致性已经由 script_json_parser.py 校验。
    这里如果出现重复页码，后者会覆盖前者。
    但正常流程不会出现该情况。
    """

    return {page.page_index: page for page in pages}


def _build_node_id(page_index: int, kind: str) -> str:
    """
    构造 Python 侧局部 nodeId。

    Java 后端落库时会再做 coursewareId + pageIndex + nodeId 的命名空间拼接，
    因此 Python 侧不需要把 coursewareId 拼进去。

    Parameters
    ----------
    page_index:
        页码，从 1 开始。
    kind:
        节点类型，例如 opening/main/transition/closing。

    Returns
    -------
    str
        稳定、短小、可读的节点 ID。
    """

    return f"n_{page_index}_{kind}"
