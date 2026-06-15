from __future__ import annotations

from urllib.parse import urlsplit

from pathlib import Path

from app.schemas.video_render import VideoRenderSegment
from app.services.video_render_service import (
    DigitalHumanOverlayClip,
    PreparedRenderSegment,
    _build_filter_graph,
    _download_audio_from_minio,
    _digital_human_lead_trim_ms,
    _effective_digital_human_max_audio_seconds,
    _estimate_digital_human_importance,
    _rewrite_internal_download_url,
    _select_digital_human_segments,
)


def _prepared_segment(
    *,
    page_index: int,
    title: str,
    script_text: str,
    knowledge_points: list[str] | None = None,
    visual_summary: str | None = None,
    duration_ms: int = 9000,
    has_real_audio: bool = True,
) -> PreparedRenderSegment:
    segment = VideoRenderSegment(
        segmentId=f"seg-{page_index}",
        pageIndex=page_index,
        title=title,
        scriptText=script_text,
        pageImagePath=f"/tmp/page-{page_index}.png",
        knowledgePoints=knowledge_points or [],
        visualSummary=visual_summary,
        audioPath=f"/tmp/segment-{page_index}.mp3" if has_real_audio else None,
        durationMs=duration_ms,
    )
    return PreparedRenderSegment(
        key=f"seg-{page_index}",
        index=page_index,
        segment=segment,
        image_path=Path(segment.page_image_path),
        audio_path=Path(segment.audio_path or f"/tmp/silent-{page_index}.m4a"),
        duration_ms=duration_ms,
        has_real_audio=has_real_audio,
    )


def test_estimate_digital_human_importance_prefers_detail_pages() -> None:
    overview = _prepared_segment(
        page_index=1,
        title="CNN Overview",
        script_text="这一页先快速说明本节结构。",
        knowledge_points=[],
    )
    detail = _prepared_segment(
        page_index=4,
        title="Convolution Layer: Example",
        script_text="这里重点解释卷积层输出尺寸为什么会变化，以及步长和填充分别如何影响输出结果。",
        knowledge_points=["stride", "padding", "output size"],
        visual_summary="输出尺寸公式和示意图",
    )

    overview_score = _estimate_digital_human_importance(overview)
    detail_score = _estimate_digital_human_importance(detail)

    assert detail_score.score > overview_score.score
    assert "detail" in detail_score.reason or "knowledge" in detail_score.reason


def test_select_digital_human_segments_respects_audio_gap_and_priority(monkeypatch) -> None:
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MAX_SEGMENTS", 2)
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MAX_SEGMENT_RATIO", 0.6)
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MIN_PAGE_GAP", 1)
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MIN_IMPORTANCE_SCORE", 0.45)
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MIN_AUDIO_SECONDS", 2)

    segments = [
        _prepared_segment(
            page_index=1,
            title="Course Overview",
            script_text="这一页先交代课程结构，不展开细节。",
        ),
        _prepared_segment(
            page_index=3,
            title="Convolution Layer: Example",
            script_text="这里通过具体数值说明卷积层的输入、卷积核、步长和填充怎样共同决定输出尺寸。",
            knowledge_points=["input volume", "stride", "padding"],
        ),
        _prepared_segment(
            page_index=4,
            title="Max Pooling",
            script_text="这里解释最大池化如何保留最强响应并完成下采样。",
            knowledge_points=["max pooling", "downsample"],
            visual_summary="2x2 pooling illustration",
        ),
        _prepared_segment(
            page_index=7,
            title="Fully Connected Layer",
            script_text="这里解释全连接层如何把前面的特征拉平后送入分类器，并综合所有特征完成最终判断。",
            knowledge_points=["flatten", "classifier"],
        ),
        _prepared_segment(
            page_index=9,
            title="Summary",
            script_text="这一页只做简短总结。",
        ),
        _prepared_segment(
            page_index=11,
            title="Feature Map Example",
            script_text="这里展示特征图的变化，但这一页没有真实音频，不应该入选。",
            has_real_audio=False,
        ),
    ]

    selected = _select_digital_human_segments(segments)
    selected_pages = [prepared.segment.page_index for prepared, _ in selected]

    assert selected_pages == [3, 7]


def test_select_digital_human_segments_returns_empty_when_all_candidates_are_low_value(monkeypatch) -> None:
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MAX_SEGMENTS", 3)
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MAX_SEGMENT_RATIO", 0.5)
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MIN_PAGE_GAP", 1)
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MIN_IMPORTANCE_SCORE", 0.7)
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MIN_AUDIO_SECONDS", 2)

    segments = [
        _prepared_segment(page_index=1, title="Agenda", script_text="本节内容安排。"),
        _prepared_segment(page_index=2, title="Summary", script_text="这一页做简单回顾。"),
        _prepared_segment(page_index=3, title="Upload Your Answer", script_text="按要求提交作业即可。"),
    ]

    assert _select_digital_human_segments(segments) == []


def test_rewrite_internal_download_url_swaps_localhost_for_minio_endpoint(monkeypatch) -> None:
    monkeypatch.setattr("app.services.video_render_service.settings.MINIO_ENDPOINT", "http://minio:9000")
    raw_url = (
        "http://localhost:9000/courseware/tts-audio/a.mp3"
        "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=abc"
    )

    rewritten = _rewrite_internal_download_url(raw_url)

    assert rewritten.startswith("http://minio:9000/courseware/tts-audio/a.mp3?")
    assert "X-Amz-Signature=abc" in rewritten


def test_download_audio_from_minio_falls_back_to_object_storage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.video_render_service.settings.MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setattr("app.services.video_render_service.settings.MINIO_ACCESS_KEY", "test-access")
    monkeypatch.setattr("app.services.video_render_service.settings.MINIO_SECRET_KEY", "test-secret")

    class DummyResponse:
        def read(self) -> bytes:
            return b"mock-audio"

        def close(self) -> None:
            return None

        def release_conn(self) -> None:
            return None

    class DummyMinio:
        def get_object(self, bucket_name: str, object_name: str) -> DummyResponse:
            assert bucket_name == "courseware"
            assert object_name == "tts-audio/test.mp3"
            return DummyResponse()

    def fake_create_minio_client(endpoint: str, secure: bool) -> DummyMinio:
        assert endpoint == "minio:9000"
        assert secure is False
        return DummyMinio()

    monkeypatch.setattr("app.services.video_render_service._create_minio_client", fake_create_minio_client)

    target = tmp_path / "segment.mp3"
    ok = _download_audio_from_minio(urlsplit("http://minio:9000/courseware/tts-audio/test.mp3"), target)

    assert ok is True
    assert target.read_bytes() == b"mock-audio"


def test_digital_human_lead_trim_ms_keeps_at_least_half_second(monkeypatch) -> None:
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_LEAD_TRIM_SECONDS", 1.5)

    assert _digital_human_lead_trim_ms(10_000) == 1_500
    assert _digital_human_lead_trim_ms(1_200) == 700
    assert _digital_human_lead_trim_ms(400) == 0


def test_effective_digital_human_max_audio_seconds_caps_wan_model(monkeypatch) -> None:
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MIN_AUDIO_SECONDS", 2)
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MAX_AUDIO_SECONDS", 14)
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_MODEL_NAME", "wan2.7-r2v")

    assert _effective_digital_human_max_audio_seconds() == 10


def test_build_filter_graph_places_overlay_at_top_right_when_margins_zero(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_OVERLAY_WIDTH_RATIO", 0.22)
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_OVERLAY_MARGIN_TOP", 0)
    monkeypatch.setattr("app.services.video_render_service.settings.DIGITAL_HUMAN_OVERLAY_MARGIN_RIGHT", 0)

    filter_graph = _build_filter_graph(
        subtitle_srt_path=tmp_path / "subtitle.srt",
        subtitle_text_path=None,
        width=1280,
        height=720,
        overlay_clip=DigitalHumanOverlayClip(
            video_path=tmp_path / "overlay.mp4",
            start_offset_ms=1500,
            visible_ms=12_000,
            score=0.8,
            reason="detail-rich title",
        ),
    )

    assert "overlay=x=W-w:y=0" in filter_graph
    assert "enable='between(t,1.500,13.500)'" in filter_graph
    assert "MarginV=6" in filter_graph
