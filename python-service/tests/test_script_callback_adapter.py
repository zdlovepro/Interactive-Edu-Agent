"""
讲稿 Java Callback Payload 适配器测试。
"""

from __future__ import annotations

from app.schemas.script import (
    PageContent,
    PageScript,
    ScriptCallbackPayload,
    ScriptGenerateRequest,
    ScriptGenerateResponse,
)
from app.services.script_callback_adapter import (
    build_failed_callback_payload,
    build_success_callback_payload,
    callback_payload_to_dict,
)


def _build_request() -> ScriptGenerateRequest:
    """构造标准两页请求。"""
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


def _build_script_response() -> ScriptGenerateResponse:
    """构造标准两页讲稿结果。"""
    return ScriptGenerateResponse(
        courseware_id="cware_001",
        opening="大家好，欢迎来到数据结构导论的学习。",
        pages=[
            PageScript(
                page_index=1,
                script="首先我们来看递归的基本概念。",
                transition="理解递归之后，我们继续看一个经典案例。",
            ),
            PageScript(
                page_index=2,
                script="斐波那契数列是递归思想的典型体现。",
                transition="以上就是本页内容的小结。",
            ),
        ],
        closing="本节课我们学习了递归及其典型应用。",
    )


def test_build_success_callback_payload_success() -> None:
    """成功回调 payload 应包含 Java DTO 所需字段。"""
    request = _build_request()
    script = _build_script_response()

    payload = build_success_callback_payload(
        request=request,
        script=script,
    )

    assert isinstance(payload, ScriptCallbackPayload)
    assert payload.coursewareId == "cware_001"
    assert payload.processStatus == "SUCCESS"
    assert payload.errorMessage is None
    assert len(payload.pages) == 2

    first_page = payload.pages[0]
    second_page = payload.pages[1]

    assert first_page.pageIndex == 1
    assert first_page.originalText == "递归是函数直接或间接调用自身的编程技术，需要有终止条件。"

    assert second_page.pageIndex == 2
    assert second_page.originalText == "斐波那契数列是递归的典型应用。"


def test_first_page_contains_opening_main_transition() -> None:
    """第一页应包含 opening、main、transition 三个节点。"""
    payload = build_success_callback_payload(
        request=_build_request(),
        script=_build_script_response(),
    )

    first_page_nodes = payload.pages[0].scripts

    assert [node.nodeId for node in first_page_nodes] == [
        "n_1_opening",
        "n_1_main",
        "n_1_transition",
    ]

    assert first_page_nodes[0].content == "大家好，欢迎来到数据结构导论的学习。"
    assert first_page_nodes[1].content == "首先我们来看递归的基本概念。"
    assert first_page_nodes[2].content == "理解递归之后，我们继续看一个经典案例。"


def test_last_page_contains_main_transition_closing() -> None:
    """最后一页应包含 main、transition、closing 三个节点。"""
    payload = build_success_callback_payload(
        request=_build_request(),
        script=_build_script_response(),
    )

    last_page_nodes = payload.pages[-1].scripts

    assert [node.nodeId for node in last_page_nodes] == [
        "n_2_main",
        "n_2_transition",
        "n_2_closing",
    ]

    assert last_page_nodes[0].content == "斐波那契数列是递归思想的典型体现。"
    assert last_page_nodes[1].content == "以上就是本页内容的小结。"
    assert last_page_nodes[2].content == "本节课我们学习了递归及其典型应用。"


def test_callback_payload_to_dict_uses_java_camel_case_fields() -> None:
    """callback_payload_to_dict 应输出 Java DTO 需要的 camelCase 字段。"""
    payload = build_success_callback_payload(
        request=_build_request(),
        script=_build_script_response(),
    )

    data = callback_payload_to_dict(payload)

    assert data["coursewareId"] == "cware_001"
    assert data["processStatus"] == "SUCCESS"
    assert data["errorMessage"] is None

    assert "courseware_id" not in data
    assert "process_status" not in data

    first_page = data["pages"][0]
    assert first_page["pageIndex"] == 1
    assert first_page["originalText"] == "递归是函数直接或间接调用自身的编程技术，需要有终止条件。"

    first_node = first_page["scripts"][0]
    assert first_node["nodeId"] == "n_1_opening"
    assert first_node["content"] == "大家好，欢迎来到数据结构导论的学习。"


def test_all_callback_nodes_have_non_empty_node_id_and_content() -> None:
    """所有 callback node 都必须有非空 nodeId 和 content。"""
    payload = build_success_callback_payload(
        request=_build_request(),
        script=_build_script_response(),
    )

    for page in payload.pages:
        for node in page.scripts:
            assert node.nodeId.strip()
            assert node.content.strip()


def test_build_failed_callback_payload_success() -> None:
    """失败回调 payload 应包含 FAILED 状态和错误信息。"""
    payload = build_failed_callback_payload(
        courseware_id="cware_001",
        error_message="大模型输出格式异常：JSON 解析失败",
    )

    assert payload.coursewareId == "cware_001"
    assert payload.processStatus == "FAILED"
    assert payload.errorMessage == "大模型输出格式异常：JSON 解析失败"
    assert payload.pages == []


def test_single_page_script_contains_opening_main_transition_closing() -> None:
    """单页课件时，同一页应同时包含 opening、main、transition、closing。"""
    request = ScriptGenerateRequest(
        courseware_id="cware_single",
        courseware_name="单页课程",
        subject="通用课程",
        pages=[
            PageContent(
                page_index=1,
                title="唯一页面",
                text_content="这是唯一一页的原始文本。",
                keywords=[],
            )
        ],
    )

    script = ScriptGenerateResponse(
        courseware_id="cware_single",
        opening="欢迎大家开始学习。",
        pages=[
            PageScript(
                page_index=1,
                script="这是唯一一页的核心讲解。",
                transition="这是本页小结。",
            )
        ],
        closing="本节课到这里结束。",
    )

    payload = build_success_callback_payload(
        request=request,
        script=script,
    )

    assert len(payload.pages) == 1

    node_ids = [node.nodeId for node in payload.pages[0].scripts]
    contents = [node.content for node in payload.pages[0].scripts]

    assert node_ids == [
        "n_1_opening",
        "n_1_main",
        "n_1_transition",
        "n_1_closing",
    ]

    assert contents == [
        "欢迎大家开始学习。",
        "这是唯一一页的核心讲解。",
        "这是本页小结。",
        "本节课到这里结束。",
    ]
