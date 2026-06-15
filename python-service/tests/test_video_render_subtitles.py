from __future__ import annotations

from app.schemas.video_render import VideoRenderSegment
from app.services.video_render_service import (
    _build_segment_subtitle_cues,
    _split_subtitle_units,
    _subtitle_text,
)


def _segment(script_text: str) -> VideoRenderSegment:
    return VideoRenderSegment(
        segmentId="seg-1",
        pageIndex=1,
        title="CNN Detail",
        scriptText=script_text,
        pageImagePath="/tmp/page-1.png",
        durationMs=9000,
    )


def test_split_subtitle_units_keeps_each_unit_within_two_lines() -> None:
    text = (
        "这一页要重点解释卷积核为什么能够提取局部特征，"
        "同时说明步长和填充会怎样影响输出尺寸。"
        "最后再补充一个简单例子，帮助你把公式和图像对应起来。"
    )

    units = _split_subtitle_units(text)

    assert units
    assert all(1 <= len(unit.splitlines()) <= 2 for unit in units)
    assert all(unit.strip() for unit in units)


def test_subtitle_text_returns_first_two_line_unit() -> None:
    segment = _segment(
        "这里先解释卷积层如何扫描输入图像，"
        "再说明卷积结果为什么会形成新的特征图。"
    )

    subtitle = _subtitle_text(segment)

    assert subtitle
    assert len(subtitle.splitlines()) <= 2


def test_build_segment_subtitle_cues_avoids_three_line_cues() -> None:
    segment = _segment(
        "这部分需要用中文讲清楚卷积核、步长、填充和输出尺寸之间的关系，"
        "不要只读 PPT，而是要把公式背后的直觉解释出来，"
        "并且给学生一个可以马上记住的判断方法。"
    )

    cues = _build_segment_subtitle_cues(segment, 12000)

    assert cues
    assert all(1 <= len(cue.text.splitlines()) <= 2 for cue in cues)
    assert cues[-1].end_ms == 12000
