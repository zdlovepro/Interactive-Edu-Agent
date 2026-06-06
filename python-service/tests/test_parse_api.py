from __future__ import annotations

from app.api.v1 import parse as parse_api
from app.schemas.parse import PageContent, ParseResult
from app.services import parse_service


def test_health_returns_code_zero(request_app):
    response = request_app("GET", "/python/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "success",
        "data": {
            "service": "AI Interactive Lecture API",
            "status": "UP",
        },
    }


def test_json_response_contains_utf8_charset(request_app):
    response = request_app("GET", "/python/v1/health")

    content_type = response.headers.get("content-type", "")
    assert "application/json" in content_type.lower()
    assert "charset=utf-8" in content_type.lower()


def test_parse_request_accepts_camel_case_fields(request_app, monkeypatch):
    captured = {}

    def fake_parse_courseware_file(request):
        captured["courseware_id"] = request.courseware_id
        captured["file_name"] = request.file_name
        captured["content_type"] = request.content_type
        return {"pages": 1, "outline": ["课程导入"], "segments": []}

    monkeypatch.setattr(parse_api, "parse_courseware_file", fake_parse_courseware_file)

    response = request_app(
        "POST",
        "/python/v1/parse",
        json={
            "coursewareId": "cware_123",
            "storage": "local",
            "key": "cware_123/demo.pptx",
            "fileName": "demo.pptx",
            "contentType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        },
    )

    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert captured == {
        "courseware_id": "cware_123",
        "file_name": "demo.pptx",
        "content_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }


def test_unknown_exception_returns_base_response(request_app, monkeypatch):
    def boom(_request):
        raise RuntimeError("sensitive internal detail")

    monkeypatch.setattr(parse_api, "parse_courseware_file", boom)

    response = request_app(
        "POST",
        "/python/v1/parse",
        json={
            "coursewareId": "cware_500",
            "storage": "local",
            "key": "cware_500/demo.pdf",
            "fileName": "demo.pdf",
            "contentType": "application/pdf",
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == 50001
    assert body["data"] is None
    assert body["message"] == "服务内部错误，请稍后重试"
    assert "sensitive internal detail" not in body["message"]


def test_parse_contract_adds_page_details_without_removing_segments():
    result = ParseResult(
        courseware_id="cware_page_details",
        file_type="pptx",
        total_pages=1,
        pages=[
            PageContent(
                page_index=1,
                text="流程图说明导入步骤",
                notes="",
                image_placeholders=["[流程图:slide_1_flow_1]", "[图表:slide_1_chart_1]"],
                formula_placeholders=["[公式:slide_1_formula_1]"],
            )
        ],
    )

    payload = parse_service._build_contract_payload(
        result,
        "demo.pptx",
        visual_summary_by_page={},
        page_images={1: "D:/tmp/page_1.png"},
    )

    assert payload["pages"] == 1
    assert payload["coursewareId"] == "cware_page_details"
    assert payload["segments"][0]["pageIndex"] == 1
    assert payload["segments"][0]["visualSummary"]
    assert payload["segments"][0]["pageImagePath"] == "D:/tmp/page_1.png"
    assert payload["pageDetails"][0]["pageNo"] == 1
    assert payload["pageDetails"][0]["text"] == "流程图说明导入步骤"
    assert payload["pageDetails"][0]["imagePath"] == "D:/tmp/page_1.png"
    assert payload["pageDetails"][0]["formulas"] == ["[公式:slide_1_formula_1]"]
    assert payload["pageDetails"][0]["charts"] == ["[图表:slide_1_chart_1]"]
    assert payload["pageDetails"][0]["diagrams"] == ["[流程图:slide_1_flow_1]"]
