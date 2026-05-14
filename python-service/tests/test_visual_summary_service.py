from __future__ import annotations

from app.schemas.parse import PageContent
from app.services.visual_summary_service import build_mock_visual_summary


def test_build_mock_visual_summary_detects_objects_from_placeholders_and_text() -> None:
    page = PageContent(
        page_index=3,
        text="表头1 | 表头2 | 表头3\n数据1 | 数据2 | 数据3",
        notes="",
        image_placeholders=["[图片:page_3_img_1]"],
        formula_placeholders=["[公式:page_3_formula_1]"],
    )

    summary = build_mock_visual_summary(page)

    assert summary.page_index == 3
    assert summary.visual_summary
    assert "表格" in summary.objects
    assert "图表/图片" in summary.objects
    assert "公式" in summary.objects


def test_build_mock_visual_summary_detects_vector_drawings_as_diagram() -> None:
    page = PageContent(
        page_index=1,
        text="",
        notes="",
        image_placeholders=["[矢量图形:page_1_drawings_120]"],
        formula_placeholders=[],
    )

    summary = build_mock_visual_summary(page)

    assert "图表/图片" in summary.objects
    assert "流程图/示意图" in summary.objects


def test_build_mock_visual_summary_detects_pptx_chart_and_flowchart_placeholders() -> None:
    page = PageContent(
        page_index=1,
        text="",
        notes="",
        image_placeholders=[
            "[图表:slide_1_chart_1]",
            "[流程图:slide_1_flow_1]",
            "[示意图:slide_1_smartart_1]",
        ],
        formula_placeholders=[],
    )

    summary = build_mock_visual_summary(page)

    assert "图表/图片" in summary.objects
    assert "图表" in summary.objects
    assert "流程图" in summary.objects
    assert "示意图" in summary.objects
