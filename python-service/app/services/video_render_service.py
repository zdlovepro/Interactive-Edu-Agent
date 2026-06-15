from __future__ import annotations

import asyncio
import json
import math
import re
import shutil
import subprocess
import textwrap
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from app.clients.dashscope_videoretalk_client import DashScopeDigitalHumanClient
from app.core.config import settings
from app.core.exceptions import AppException, BUSINESS_VALIDATION_FAILED, PythonServiceException
from app.schemas.video_render import (
    VideoRenderRequest,
    VideoRenderResult,
    VideoRenderSegment,
    VideoRenderTimelineItem,
)
from app.utils.logger import logger


@dataclass(frozen=True)
class SubtitleCue:
    text: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class PreparedRenderSegment:
    key: str
    index: int
    segment: VideoRenderSegment
    image_path: Path
    audio_path: Path
    duration_ms: int
    has_real_audio: bool


@dataclass(frozen=True)
class DigitalHumanSelection:
    score: float
    reason: str


@dataclass(frozen=True)
class DigitalHumanOverlayClip:
    video_path: Path
    start_offset_ms: int
    visible_ms: int
    score: float
    reason: str


_SUBTITLE_SENTENCE_BREAK_RE = re.compile(r"(?<=[。！？!?])\s*")
_SUBTITLE_CLAUSE_BREAK_RE = re.compile(r"(?<=[，,；;：:])\s*")
_SUBTITLE_LINE_WIDTH = 20.5
_SUBTITLE_CHUNK_WIDTH = 34.0
_SUBTITLE_MAX_LINES = 2


_DETAIL_TITLE_PATTERNS = (
    r"\bexample\b",
    r"\bformula\b",
    r"\bderivation\b",
    r"\bconvolution\b",
    r"\bpooling\b",
    r"\bfully connected\b",
    r"\bactivation\b",
    r"\bfeature map\b",
    r"\breceptive field\b",
    r"\boutput size\b",
    r"\bparameters?\b",
    r"公式",
    r"推导",
    r"案例",
    r"例题",
    r"概念",
    r"原理",
    r"卷积",
    r"池化",
    r"全连接",
    r"参数",
    r"尺寸",
    r"特征",
)

_SKIP_TITLE_PATTERNS = (
    r"\boverview\b",
    r"\bagenda\b",
    r"\boutline\b",
    r"\bsummary\b",
    r"\breview\b",
    r"\bcontents\b",
    r"\bupload your answer\b",
    r"\bhomework\b",
    r"\bthank",
    r"目录",
    r"总览",
    r"概览",
    r"小结",
    r"总结",
    r"回顾",
    r"练习",
    r"作业",
)

_DETAIL_SCRIPT_PATTERNS = (
    r"为什么",
    r"意味着",
    r"可以理解为",
    r"本质上",
    r"输入",
    r"输出",
    r"特征",
    r"参数",
    r"卷积",
    r"池化",
    r"维度",
    r"通道",
    r"步长",
    r"填充",
    r"kernel",
    r"stride",
    r"padding",
    r"feature",
    r"parameter",
    r"output",
)


def render_courseware_video(request: VideoRenderRequest) -> dict[str, object]:
    if not request.segments:
        raise AppException(BUSINESS_VALIDATION_FAILED, "video render requires at least one segment")

    _ensure_executable("ffmpeg")
    _ensure_executable("ffprobe")

    output_dir = _resolve_output_dir(request)
    input_dir = output_dir / "input"
    audio_dir = output_dir / "audio"
    part_dir = output_dir / "parts"
    hls_dir = output_dir / "hls"

    for directory in (input_dir, audio_dir, part_dir, hls_dir):
        if directory.exists() and directory in (part_dir, hls_dir):
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)

    input_manifest_path = output_dir / "video_render_input.json"
    input_manifest_path.write_text(
        json.dumps(request.model_dump(by_alias=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    ordered_segments = sorted(request.segments, key=lambda item: item.page_index)
    prepared_segments = _prepare_segments(ordered_segments, audio_dir, request.backend_base_url)
    overlay_plan, overlay_manifest = _build_digital_human_overlays(prepared_segments, input_dir)
    if overlay_manifest:
        (output_dir / "digital_human_manifest.json").write_text(
            json.dumps(overlay_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    timeline: list[VideoRenderTimelineItem] = []
    part_paths: list[Path] = []
    cursor_ms = 0

    for prepared in prepared_segments:
        part_path = part_dir / f"part_{prepared.index:03d}.mp4"
        part_subtitle_path = input_dir / f"subtitle_{prepared.index:03d}.srt"
        cues = _build_segment_subtitle_cues(prepared.segment, prepared.duration_ms)
        part_subtitle_path.write_text(_build_local_srt(cues), encoding="utf-8")

        _render_part(
            image_path=prepared.image_path,
            audio_path=prepared.audio_path,
            subtitle_srt_path=part_subtitle_path,
            fallback_subtitle_text=_subtitle_text(prepared.segment),
            output_path=part_path,
            width=request.width,
            height=request.height,
            overlay_clip=overlay_plan.get(prepared.key),
        )
        part_paths.append(part_path)

        end_ms = cursor_ms + prepared.duration_ms
        timeline.append(
            VideoRenderTimelineItem(
                segmentId=prepared.segment.segment_id or f"seg_{prepared.index:03d}",
                pageIndex=prepared.segment.page_index,
                title=prepared.segment.title,
                startMs=cursor_ms,
                endMs=end_ms,
                durationMs=prepared.duration_ms,
                pageImagePath=str(prepared.image_path),
                audioPath=str(prepared.audio_path),
            )
        )
        cursor_ms = end_ms

    timeline_path = output_dir / "timeline.json"
    timeline_path.write_text(
        json.dumps([item.model_dump(by_alias=True) for item in timeline], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    subtitle_path = output_dir / "subtitles.srt"
    subtitle_path.write_text(_build_srt(timeline, ordered_segments), encoding="utf-8")

    mp4_path = output_dir / "lecture.mp4"
    _concat_parts(part_paths, mp4_path)
    _build_hls(mp4_path, hls_dir, request.hls_segment_seconds)

    result = VideoRenderResult(
        coursewareId=request.courseware_id,
        outputDir=str(output_dir),
        inputManifestPath=str(input_manifest_path),
        timelinePath=str(timeline_path),
        subtitlePath=str(subtitle_path),
        mp4Path=str(mp4_path),
        hlsPlaylistPath=str(hls_dir / "index.m3u8"),
        durationMs=cursor_ms,
        segmentCount=len(timeline),
        timeline=timeline,
    )
    logger.info(
        "Courseware video render finished. coursewareId=%s segments=%s durationMs=%s digitalHumanSegments=%s mp4=%s",
        request.courseware_id,
        len(timeline),
        cursor_ms,
        len(overlay_plan),
        mp4_path,
    )
    return result.model_dump(by_alias=True)


def _prepare_segments(
    segments: list[VideoRenderSegment],
    audio_dir: Path,
    backend_base_url: str | None,
) -> list[PreparedRenderSegment]:
    prepared_segments: list[PreparedRenderSegment] = []
    for index, segment in enumerate(segments, start=1):
        image_path = _resolve_existing_file(segment.page_image_path, "page image")
        has_real_audio = bool(segment.audio_path or segment.audio_url)
        audio_path = _resolve_or_create_audio(segment, audio_dir, backend_base_url)
        duration_ms = segment.duration_ms or _probe_audio_duration_ms(audio_path)
        if duration_ms <= 0:
            duration_ms = _estimate_duration_ms(segment.script_text)
        prepared_segments.append(
            PreparedRenderSegment(
                key=_segment_key(segment, index),
                index=index,
                segment=segment,
                image_path=image_path,
                audio_path=audio_path,
                duration_ms=duration_ms,
                has_real_audio=has_real_audio,
            )
        )
    return prepared_segments


def _build_digital_human_overlays(
    prepared_segments: list[PreparedRenderSegment],
    input_dir: Path,
) -> tuple[dict[str, DigitalHumanOverlayClip], list[dict[str, object]]]:
    if not _digital_human_enabled():
        return {}, []

    reference_image_path = _resolve_digital_human_reference_image()
    if reference_image_path is None:
        logger.info("Digital human rendering skipped because no reference image path is configured.")
        return {}, []

    selected = _select_digital_human_segments(prepared_segments)
    if not selected:
        logger.info("Digital human rendering skipped because no high-value segments were selected.")
        return {}, []

    return asyncio.run(_generate_digital_human_overlays(selected, reference_image_path, input_dir))


async def _generate_digital_human_overlays(
    selected_segments: list[tuple[PreparedRenderSegment, DigitalHumanSelection]],
    reference_image_path: Path,
    input_dir: Path,
) -> tuple[dict[str, DigitalHumanOverlayClip], list[dict[str, object]]]:
    overlay_plan: dict[str, DigitalHumanOverlayClip] = {}
    manifest: list[dict[str, object]] = []

    async with DashScopeDigitalHumanClient() as client:
        for prepared, selection in selected_segments:
            overlay_audio_path = input_dir / f"digital_human_audio_{prepared.index:03d}.mp3"
            overlay_video_path = input_dir / f"digital_human_video_{prepared.index:03d}.mp4"

            visible_ms = _create_overlay_audio_clip(prepared.audio_path, overlay_audio_path)
            if visible_ms < settings.DIGITAL_HUMAN_MIN_AUDIO_SECONDS * 1000:
                manifest.append(
                    {
                        "pageIndex": prepared.segment.page_index,
                        "segmentId": prepared.segment.segment_id,
                        "status": "skipped",
                        "reason": "segment audio is shorter than the digital human minimum duration",
                        "score": round(selection.score, 3),
                    }
                )
                continue

            try:
                prompt = _build_digital_human_prompt(prepared.segment, visible_ms)
                await client.render_clip(
                    reference_image_path=reference_image_path,
                    reference_voice_path=overlay_audio_path,
                    prompt=prompt,
                    output_path=overlay_video_path,
                    duration_seconds=_overlay_duration_seconds(visible_ms),
                )
                start_offset_ms, final_visible_ms = _finalize_digital_human_clip(overlay_video_path, visible_ms)
                overlay_plan[prepared.key] = DigitalHumanOverlayClip(
                    video_path=overlay_video_path,
                    start_offset_ms=start_offset_ms,
                    visible_ms=final_visible_ms,
                    score=selection.score,
                    reason=selection.reason,
                )
                manifest.append(
                    {
                        "pageIndex": prepared.segment.page_index,
                        "segmentId": prepared.segment.segment_id,
                        "status": "success",
                        "reason": selection.reason,
                        "score": round(selection.score, 3),
                        "overlayStartSeconds": round(start_offset_ms / 1000, 3),
                        "overlaySeconds": round(final_visible_ms / 1000, 3),
                        "videoPath": str(overlay_video_path),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Digital human generation failed. pageIndex=%s reason=%s",
                    prepared.segment.page_index,
                    str(exc),
                )
                manifest.append(
                    {
                        "pageIndex": prepared.segment.page_index,
                        "segmentId": prepared.segment.segment_id,
                        "status": "failed",
                        "reason": str(exc),
                        "score": round(selection.score, 3),
                    }
                )

    return overlay_plan, manifest


def _digital_human_enabled() -> bool:
    if not settings.DIGITAL_HUMAN_ENABLED:
        return False
    if not (settings.DIGITAL_HUMAN_API_KEY or "").strip():
        logger.warning("Digital human rendering is enabled but DIGITAL_HUMAN_API_KEY is empty.")
        return False
    return True


def _resolve_digital_human_reference_image() -> Path | None:
    configured = (settings.DIGITAL_HUMAN_REFERENCE_IMAGE_PATH or "").strip()
    if configured:
        return _resolve_existing_file(configured, "digital human reference image")

    workspace_root = Path("/workspace")
    if not workspace_root.exists():
        return None

    image_candidates = sorted(
        (
            path
            for path in workspace_root.iterdir()
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ),
        key=lambda item: item.stat().st_size,
        reverse=True,
    )
    if not image_candidates:
        return None

    selected = image_candidates[0].resolve()
    logger.info("Digital human reference image auto-selected. path=%s", selected)
    return selected


def _select_digital_human_segments(
    prepared_segments: list[PreparedRenderSegment],
) -> list[tuple[PreparedRenderSegment, DigitalHumanSelection]]:
    candidates: list[tuple[PreparedRenderSegment, DigitalHumanSelection]] = []
    min_duration_ms = settings.DIGITAL_HUMAN_MIN_AUDIO_SECONDS * 1000

    for prepared in prepared_segments:
        if not prepared.has_real_audio or prepared.duration_ms < min_duration_ms:
            continue
        selection = _estimate_digital_human_importance(prepared)
        if selection.score >= settings.DIGITAL_HUMAN_MIN_IMPORTANCE_SCORE:
            candidates.append((prepared, selection))

    if not candidates:
        return []

    max_segments = max(
        1,
        min(
            settings.DIGITAL_HUMAN_MAX_SEGMENTS,
            math.ceil(len(prepared_segments) * max(0.05, settings.DIGITAL_HUMAN_MAX_SEGMENT_RATIO)),
        ),
    )
    min_page_gap = max(0, settings.DIGITAL_HUMAN_MIN_PAGE_GAP)

    chosen: list[tuple[PreparedRenderSegment, DigitalHumanSelection]] = []
    chosen_pages: list[int] = []

    for prepared, selection in sorted(
        candidates,
        key=lambda item: (-item[1].score, item[0].segment.page_index),
    ):
        if any(abs(prepared.segment.page_index - page_index) <= min_page_gap for page_index in chosen_pages):
            continue
        chosen.append((prepared, selection))
        chosen_pages.append(prepared.segment.page_index)
        if len(chosen) >= max_segments:
            break

    chosen.sort(key=lambda item: item[0].segment.page_index)
    logger.info(
        "Digital human segment plan prepared. selected=%s candidates=%s maxSegments=%s",
        len(chosen),
        len(candidates),
        max_segments,
    )
    return chosen


def _estimate_digital_human_importance(prepared: PreparedRenderSegment) -> DigitalHumanSelection:
    title = (prepared.segment.title or "").strip()
    script_text = (prepared.segment.script_text or "").strip()
    knowledge_points = [item.strip() for item in prepared.segment.knowledge_points if item and item.strip()]
    visual_summary = (prepared.segment.visual_summary or "").strip()

    lowered_title = title.lower()
    lowered_script = script_text.lower()
    score = 0.18
    reasons: list[str] = []

    if _matches_any_pattern(lowered_title, _DETAIL_TITLE_PATTERNS):
        score += 0.32
        reasons.append("detail-rich title")

    if _matches_any_pattern(lowered_title, (r"\bexample\b", r"\bformula\b", r"例题", r"案例", r"公式", r"推导")):
        score += 0.08
        reasons.append("example or formula emphasis")

    if _matches_any_pattern(lowered_title, _SKIP_TITLE_PATTERNS):
        score -= 0.42
        reasons.append("overview-like title")

    if knowledge_points:
        score += min(0.18, 0.06 * len(knowledge_points))
        reasons.append("knowledge points available")

    if visual_summary:
        score += 0.08
        reasons.append("visual summary available")

    normalized_script_length = len(re.sub(r"\s+", "", script_text))
    if normalized_script_length >= 140:
        score += 0.22
        reasons.append("long explanation")
    elif normalized_script_length >= 90:
        score += 0.15
        reasons.append("medium explanation")
    elif normalized_script_length >= 60:
        score += 0.08
        reasons.append("compact explanation")

    if _matches_any_pattern(lowered_script, _DETAIL_SCRIPT_PATTERNS):
        score += 0.12
        reasons.append("conceptual explanation cues")

    if prepared.segment.page_index == 1:
        score -= 0.10
        reasons.append("first page penalty")

    score = max(0.0, min(1.0, score))
    reason = ", ".join(reasons) if reasons else "general lecture explanation"
    return DigitalHumanSelection(score=score, reason=reason)


def _matches_any_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _create_overlay_audio_clip(source_audio_path: Path, output_path: Path) -> int:
    total_ms = _probe_audio_duration_ms(source_audio_path)
    if total_ms <= 0:
        return 0

    min_ms = max(1, settings.DIGITAL_HUMAN_MIN_AUDIO_SECONDS) * 1000
    max_ms = _effective_digital_human_max_audio_seconds() * 1000
    clip_ms = min(total_ms, max_ms)
    if clip_ms < min_ms:
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_audio_path),
        "-vn",
        "-t",
        f"{clip_ms / 1000:.3f}",
        "-ac",
        "1",
        "-ar",
        "24000",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(output_path),
    ]
    _run(command, f"create digital human audio clip {output_path.name}")
    return _probe_audio_duration_ms(output_path)


def _effective_digital_human_max_audio_seconds() -> int:
    configured = max(settings.DIGITAL_HUMAN_MIN_AUDIO_SECONDS, settings.DIGITAL_HUMAN_MAX_AUDIO_SECONDS)
    model_name = (settings.DIGITAL_HUMAN_MODEL_NAME or "").strip().lower()
    if "wan2.7-r2v" in model_name:
        return min(configured, 10)
    return configured


def _digital_human_lead_trim_ms(total_ms: int) -> int:
    configured_trim_ms = max(0, int(round(max(0.0, settings.DIGITAL_HUMAN_LEAD_TRIM_SECONDS) * 1000)))
    if configured_trim_ms <= 0 or total_ms <= 500:
        return 0
    return min(configured_trim_ms, max(0, total_ms - 500))


def _overlay_duration_seconds(visible_ms: int) -> int:
    return max(2, min(15, round(max(1, visible_ms) / 1000)))


def _build_digital_human_prompt(segment: VideoRenderSegment, visible_ms: int) -> str:
    spoken_text = _select_digital_human_spoken_text(segment, visible_ms)
    title = (segment.title or "当前课件页").strip()
    return (
        "参考图片中的人物是一位中文课程讲师。"
        "请保持人物身份、脸部、发型和服装一致，生成固定机位的 16:9 半身讲解视频，"
        "人物面对镜头，自然说话并带轻微手势，背景保持简洁干净。"
        "不要添加字幕、水印、额外人物、额外道具或大幅镜头运动。"
        f"当前讲解主题：{title}。"
        f"请用自然中文讲解以下内容：{spoken_text}"
    )


def _select_digital_human_spoken_text(segment: VideoRenderSegment, visible_ms: int) -> str:
    raw_text = (segment.script_text or segment.title or f"第{segment.page_index}页").strip()
    units = _split_subtitle_units(raw_text)
    if not units:
        return raw_text

    target_chars = max(24, min(92, int(_overlay_duration_seconds(visible_ms) * 8)))
    chosen: list[str] = []
    consumed = 0
    for unit in units:
        collapsed = unit.replace("\n", "")
        if not collapsed:
            continue
        chosen.append(collapsed)
        consumed += len(re.sub(r"\s+", "", collapsed))
        if consumed >= target_chars:
            break

    spoken_text = "".join(chosen).strip()
    return spoken_text or raw_text


def _strip_audio_track(video_path: Path) -> None:
    silent_output = video_path.with_name(f"{video_path.stem}.silent{video_path.suffix}")
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-an",
        "-c:v",
        "copy",
        str(silent_output),
    ]
    _run(command, f"strip digital human audio {video_path.name}")
    silent_output.replace(video_path)


def _finalize_digital_human_clip(video_path: Path, requested_visible_ms: int) -> tuple[int, int]:
    original_duration_ms = _probe_media_duration_ms(video_path)
    if original_duration_ms <= 0:
        _strip_audio_track(video_path)
        return 0, requested_visible_ms

    trim_ms = _digital_human_lead_trim_ms(original_duration_ms)
    normalized_output = video_path.with_name(f"{video_path.stem}.normalized{video_path.suffix}")
    command = ["ffmpeg", "-y"]
    if trim_ms > 0:
        command.extend(["-ss", f"{trim_ms / 1000:.3f}"])
    command.extend(
        [
            "-i",
            str(video_path),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(normalized_output),
        ]
    )
    _run(command, f"normalize digital human clip {video_path.name}")
    normalized_output.replace(video_path)

    final_duration_ms = _probe_media_duration_ms(video_path)
    if final_duration_ms <= 0:
        final_duration_ms = max(0, requested_visible_ms - trim_ms)
    return trim_ms, min(max(0, requested_visible_ms - trim_ms), final_duration_ms)


def _resolve_output_dir(request: VideoRenderRequest) -> Path:
    render_root = Path(settings.RENDER_BASE_DIR).expanduser().resolve()
    raw_output = request.output_dir or str(render_root / request.courseware_id / "video")
    output_dir = Path(raw_output).expanduser()
    if not output_dir.is_absolute():
        output_dir = render_root / output_dir
    output_dir = output_dir.resolve()

    if not output_dir.is_relative_to(render_root):
        raise AppException(BUSINESS_VALIDATION_FAILED, "video output_dir must stay under RENDER_BASE_DIR")

    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _resolve_existing_file(raw_path: str, label: str) -> Path:
    path = Path(raw_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise AppException(BUSINESS_VALIDATION_FAILED, f"{label} not found: {path}")
    return path


def _resolve_optional_existing_file(raw_path: str | None, label: str) -> Path | None:
    if not raw_path or not raw_path.strip():
        return None
    return _resolve_existing_file(raw_path, label)


def _resolve_or_create_audio(segment: VideoRenderSegment, audio_dir: Path, backend_base_url: str | None) -> Path:
    if segment.audio_path:
        return _resolve_existing_file(segment.audio_path, "audio")

    target = audio_dir / f"segment_{segment.page_index:03d}.audio"
    if segment.audio_url:
        return _download_audio(segment.audio_url, target, backend_base_url)

    duration_ms = segment.duration_ms or _estimate_duration_ms(segment.script_text)
    silent_path = audio_dir / f"segment_{segment.page_index:03d}_silent.m4a"
    _create_silent_audio(silent_path, duration_ms)
    return silent_path


def _download_audio(raw_url: str, target: Path, backend_base_url: str | None) -> Path:
    url = raw_url.strip()
    if url.startswith("/"):
        if not backend_base_url:
            raise AppException(BUSINESS_VALIDATION_FAILED, "relative audioUrl requires backendBaseUrl")
        url = urljoin(backend_base_url.rstrip("/") + "/", url.lstrip("/"))

    url = _rewrite_internal_download_url(url)
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise AppException(BUSINESS_VALIDATION_FAILED, f"unsupported audioUrl scheme: {parsed.scheme}")

    suffix = Path(parsed.path).suffix or ".audio"
    target = target.with_suffix(suffix)
    try:
        with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - URL comes from trusted backend state.
            target.write_bytes(response.read())
    except Exception as exc:  # noqa: BLE001
        if _download_audio_from_minio(parsed, target):
            return target
        raise PythonServiceException(f"failed to download segment audio: {parsed.netloc}") from exc

    if target.stat().st_size <= 0:
        raise PythonServiceException("downloaded segment audio is empty")
    return target


def _download_audio_from_minio(parsed_url: object, target: Path) -> bool:
    if not hasattr(parsed_url, "path"):
        return False

    raw_path = getattr(parsed_url, "path", "") or ""
    object_path = raw_path.lstrip("/")
    if "/" not in object_path:
        return False

    bucket_name, object_name = object_path.split("/", 1)
    endpoint = urlsplit(settings.MINIO_ENDPOINT or "").netloc
    if not endpoint or not settings.MINIO_ACCESS_KEY or not settings.MINIO_SECRET_KEY:
        return False

    client = _create_minio_client(endpoint, urlsplit(settings.MINIO_ENDPOINT).scheme == "https")
    try:
        response = client.get_object(bucket_name, object_name)
        try:
            target.write_bytes(response.read())
        finally:
            response.close()
            response.release_conn()
    except Exception:  # noqa: BLE001
        return False

    return target.exists() and target.stat().st_size > 0


def _create_minio_client(endpoint: str, secure: bool) -> object:
    from minio import Minio

    return Minio(
        endpoint,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=secure,
    )


def _rewrite_internal_download_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"}:
        return raw_url

    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        return raw_url

    minio_endpoint = (settings.MINIO_ENDPOINT or "").strip()
    if not minio_endpoint:
        return raw_url

    minio_parsed = urlsplit(minio_endpoint)
    if minio_parsed.scheme not in {"http", "https"} or not minio_parsed.netloc:
        return raw_url

    return urlunsplit((minio_parsed.scheme, minio_parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def _create_silent_audio(output_path: Path, duration_ms: int) -> None:
    duration_seconds = max(0.5, duration_ms / 1000)
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=24000",
        "-t",
        f"{duration_seconds:.3f}",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        str(output_path),
    ]
    _run(command, "create silent audio")


def _render_part(
    image_path: Path,
    audio_path: Path,
    subtitle_srt_path: Path,
    fallback_subtitle_text: str,
    output_path: Path,
    width: int,
    height: int,
    overlay_clip: DigitalHumanOverlayClip | None = None,
) -> None:
    filter_graph = _build_filter_graph(
        subtitle_srt_path=subtitle_srt_path,
        subtitle_text_path=None,
        width=width,
        height=height,
        overlay_clip=overlay_clip,
    )
    command = _build_render_command(image_path, audio_path, output_path, filter_graph, overlay_clip)

    try:
        _run(command, f"render video part {output_path.name}")
    except PythonServiceException as exc:
        logger.warning(
            "Subtitle filter failed, fallback to drawtext. part=%s reason=%s",
            output_path.name,
            exc,
        )
        subtitle_text_path = subtitle_srt_path.with_suffix(".txt")
        subtitle_text_path.write_text(fallback_subtitle_text, encoding="utf-8")
        fallback_filter_graph = _build_filter_graph(
            subtitle_srt_path=None,
            subtitle_text_path=subtitle_text_path,
            width=width,
            height=height,
            overlay_clip=overlay_clip,
        )
        fallback_command = _build_render_command(
            image_path,
            audio_path,
            output_path,
            fallback_filter_graph,
            overlay_clip,
        )
        _run(fallback_command, f"render video part with drawtext fallback {output_path.name}")


def _build_render_command(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    filter_graph: str,
    overlay_clip: DigitalHumanOverlayClip | None,
) -> list[str]:
    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-framerate",
        "30",
        "-i",
        str(image_path),
        "-i",
        str(audio_path),
    ]
    if overlay_clip is not None:
        command.extend(["-i", str(overlay_clip.video_path)])

    command.extend(
        [
            "-filter_complex",
            filter_graph,
            "-map",
            "[vout]",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            str(output_path),
        ]
    )
    return command


def _build_filter_graph(
    *,
    subtitle_srt_path: Path | None,
    subtitle_text_path: Path | None,
    width: int,
    height: int,
    overlay_clip: DigitalHumanOverlayClip | None,
) -> str:
    base_scale = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black[base]"
    )
    steps = [base_scale]
    current_label = "base"

    if overlay_clip is not None:
        overlay_width = max(160, int(width * max(0.08, settings.DIGITAL_HUMAN_OVERLAY_WIDTH_RATIO)))
        overlay_start_seconds = max(0.0, overlay_clip.start_offset_ms / 1000)
        overlay_seconds = max(0.5, overlay_clip.visible_ms / 1000)
        margin_top = max(0, settings.DIGITAL_HUMAN_OVERLAY_MARGIN_TOP)
        margin_right = max(0, settings.DIGITAL_HUMAN_OVERLAY_MARGIN_RIGHT)
        x_expr = "W-w" if margin_right == 0 else f"W-w-{margin_right}"
        y_expr = "0" if margin_top == 0 else str(margin_top)
        steps.extend(
            [
                f"[2:v]scale={overlay_width}:-2:flags=lanczos[avatar]",
                (
                f"[base][avatar]overlay="
                f"x={x_expr}:y={y_expr}:eof_action=pass:"
                f"enable='between(t,{overlay_start_seconds:.3f},{overlay_start_seconds + overlay_seconds:.3f})'[composite]"
                ),
            ]
        )
        current_label = "composite"

    if subtitle_srt_path is not None:
        steps.append(
            f"[{current_label}]subtitles='{_escape_filter_path(subtitle_srt_path)}':"
            "force_style='Alignment=2,MarginV=6,FontSize=16,Outline=1,Shadow=0,WrapStyle=2'[vout]"
        )
    elif subtitle_text_path is not None:
        steps.append(f"[{current_label}]{_build_drawtext_filter(subtitle_text_path)}[vout]")
    else:
        steps.append(f"[{current_label}]copy[vout]")

    return ";".join(steps)


def _build_drawtext_filter(subtitle_text_path: Path) -> str:
    drawtext_options = [
        *_fontfile_filter_options(),
        "fontcolor=white",
        "fontsize=24",
        "box=1",
        "boxcolor=black@0.58",
        "boxborderw=14",
        "x=(w-text_w)/2",
        "y=h-text_h-10",
        f"textfile='{_escape_filter_path(subtitle_text_path)}'",
    ]
    return f"drawtext={':'.join(drawtext_options)}"


def _concat_parts(part_paths: list[Path], output_path: Path) -> None:
    concat_file = output_path.parent / "concat.txt"
    concat_file.write_text(
        "\n".join(f"file '{path.as_posix()}'" for path in part_paths),
        encoding="utf-8",
    )
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        str(output_path),
    ]
    _run(command, "concat video parts")


def _build_hls(mp4_path: Path, hls_dir: Path, hls_segment_seconds: int) -> None:
    if hls_dir.exists():
        shutil.rmtree(hls_dir)
    hls_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(mp4_path),
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        "-f",
        "hls",
        "-hls_time",
        str(max(1, hls_segment_seconds)),
        "-hls_playlist_type",
        "vod",
        "-hls_segment_filename",
        str(hls_dir / "segment-%03d.ts"),
        str(hls_dir / "index.m3u8"),
    ]
    _run(command, "build hls")


def _probe_audio_duration_ms(audio_path: Path) -> int:
    return _probe_media_duration_ms(audio_path)


def _probe_media_duration_ms(media_path: Path) -> int:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(media_path),
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            return 0
        seconds = float((completed.stdout or "").strip())
        return max(1, int(math.ceil(seconds * 1000)))
    except Exception:  # noqa: BLE001
        return 0


def _estimate_duration_ms(text: str | None) -> int:
    length = len((text or "").strip())
    seconds = min(30, max(4, math.ceil(length / 4)))
    return seconds * 1000


def _subtitle_text(segment: VideoRenderSegment) -> str:
    text = " ".join((segment.script_text or segment.title or f"Page {segment.page_index}").split())
    if not text:
        return f"Page {segment.page_index}"
    lines = textwrap.wrap(text, width=30, break_long_words=True, replace_whitespace=False)
    return "\n".join(lines[:2])


def _build_segment_subtitle_cues(segment: VideoRenderSegment, duration_ms: int) -> list[SubtitleCue]:
    units = _split_subtitle_units(segment.script_text or segment.title or f"Page {segment.page_index}")
    if not units:
        units = [segment.title or f"Page {segment.page_index}"]

    weights = [max(1, len(re.sub(r"\s+", "", unit))) for unit in units]
    durations = _allocate_cue_durations(duration_ms, weights)

    cues: list[SubtitleCue] = []
    cursor = 0
    for index, unit in enumerate(units):
        cue_duration = durations[index]
        end_ms = duration_ms if index == len(units) - 1 else min(duration_ms, cursor + cue_duration)
        cues.append(SubtitleCue(text=unit, start_ms=cursor, end_ms=max(cursor + 300, end_ms)))
        cursor = max(cursor + 300, end_ms)

    if cues:
        cues[-1] = SubtitleCue(text=cues[-1].text, start_ms=cues[-1].start_ms, end_ms=duration_ms)
    return cues


def _split_subtitle_units(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return []

    primary_parts = re.split(r"(?<=[。！？?!；;])\s*", normalized)
    units: list[str] = []
    for part in primary_parts:
        part = part.strip()
        if not part:
            continue

        if len(part) > 34:
            secondary_parts = re.split(r"(?<=[，,:：])\s*", part)
            for secondary in secondary_parts:
                secondary = secondary.strip()
                if secondary:
                    units.append(secondary)
        else:
            units.append(part)

    merged: list[str] = []
    for unit in units:
        if merged and len(unit) <= 8:
            merged[-1] = f"{merged[-1]} {unit}".strip()
        else:
            merged.append(unit)

    if len(merged) > 6:
        merged = merged[:5] + [" ".join(merged[5:]).strip()]
    return merged


def _allocate_cue_durations(total_ms: int, weights: list[int]) -> list[int]:
    if not weights:
        return []

    count = len(weights)
    if count == 1:
        return [max(600, total_ms)]

    minimum_ms = 1100
    if total_ms <= count * minimum_ms:
        base = max(450, total_ms // count)
        durations = [base] * count
        durations[-1] += total_ms - sum(durations)
        return durations

    total_weight = sum(weights)
    durations = [max(minimum_ms, round(total_ms * weight / total_weight)) for weight in weights]
    diff = sum(durations) - total_ms

    while diff > 0:
        changed = False
        for index in range(len(durations)):
            if diff <= 0:
                break
            if durations[index] > minimum_ms:
                durations[index] -= 1
                diff -= 1
                changed = True
        if not changed:
            break

    while diff < 0:
        for index in range(len(durations)):
            if diff >= 0:
                break
            durations[index] += 1
            diff += 1

    return durations


def _build_local_srt(cues: list[SubtitleCue]) -> str:
    return "\n".join(
        "\n".join(
            [
                str(index),
                f"{_format_srt_time(cue.start_ms)} --> {_format_srt_time(cue.end_ms)}",
                cue.text,
                "",
            ]
        )
        for index, cue in enumerate(cues, start=1)
    )


def _build_srt(timeline: list[VideoRenderTimelineItem], segments: list[VideoRenderSegment]) -> str:
    segments_by_page = {item.page_index: item for item in segments}
    blocks: list[str] = []
    subtitle_index = 1

    for item in timeline:
        segment = segments_by_page.get(item.page_index)
        if segment is None:
            cues = [SubtitleCue(text=item.title or f"Page {item.page_index}", start_ms=0, end_ms=item.duration_ms)]
        else:
            cues = _build_segment_subtitle_cues(segment, item.duration_ms)

        for cue in cues:
            blocks.append(
                "\n".join(
                    [
                        str(subtitle_index),
                        f"{_format_srt_time(item.start_ms + cue.start_ms)} --> {_format_srt_time(item.start_ms + cue.end_ms)}",
                        cue.text,
                        "",
                    ]
                )
            )
            subtitle_index += 1

    return "\n".join(blocks)


def _subtitle_text(segment: VideoRenderSegment) -> str:
    units = _split_subtitle_units(segment.script_text or segment.title or f"Page {segment.page_index}")
    if not units:
        return f"Page {segment.page_index}"
    return units[0]


def _build_segment_subtitle_cues(segment: VideoRenderSegment, duration_ms: int) -> list[SubtitleCue]:
    units = _split_subtitle_units(segment.script_text or segment.title or f"Page {segment.page_index}")
    if not units:
        units = [segment.title or f"Page {segment.page_index}"]

    weights = [max(1, len(re.sub(r"\s+", "", unit.replace("\n", "")))) for unit in units]
    durations = _allocate_cue_durations(duration_ms, weights)

    cues: list[SubtitleCue] = []
    cursor = 0
    for index, unit in enumerate(units):
        cue_duration = durations[index]
        end_ms = duration_ms if index == len(units) - 1 else min(duration_ms, cursor + cue_duration)
        cues.append(SubtitleCue(text=unit, start_ms=cursor, end_ms=max(cursor + 320, end_ms)))
        cursor = max(cursor + 320, end_ms)

    if cues:
        cues[-1] = SubtitleCue(text=cues[-1].text, start_ms=cues[-1].start_ms, end_ms=duration_ms)
    return cues


def _split_subtitle_units(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return []

    units: list[str] = []
    sentences = [part.strip() for part in _SUBTITLE_SENTENCE_BREAK_RE.split(normalized) if part.strip()]
    if not sentences:
        sentences = [normalized]

    for sentence in sentences:
        clauses = [part.strip() for part in _SUBTITLE_CLAUSE_BREAK_RE.split(sentence) if part.strip()]
        if not clauses:
            clauses = [sentence]
        units.extend(_chunk_subtitle_clauses(clauses))

    filtered_units = [unit for unit in units if unit.strip()]
    return filtered_units[:8]


def _chunk_subtitle_clauses(clauses: list[str]) -> list[str]:
    chunks: list[str] = []
    current = ""
    for clause in clauses:
        candidate = f"{current}{clause}" if current else clause
        if current and _display_width(candidate) > _SUBTITLE_CHUNK_WIDTH:
            chunks.extend(_split_subtitle_display_units(current))
            current = clause
        else:
            current = candidate

    if current:
        chunks.extend(_split_subtitle_display_units(current))
    return chunks


def _split_subtitle_display_units(text: str) -> list[str]:
    lines = _split_display_lines(text, _SUBTITLE_LINE_WIDTH)
    if not lines:
        return []

    units: list[str] = []
    for index in range(0, len(lines), _SUBTITLE_MAX_LINES):
        units.append("\n".join(lines[index : index + _SUBTITLE_MAX_LINES]))
    return units


def _split_display_lines(text: str, max_line_width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        if char == "\n":
            if current.strip():
                lines.append(current.strip())
            current = ""
            continue

        candidate = f"{current}{char}"
        if current and _display_width(candidate) > max_line_width:
            lines.append(current.strip())
            current = char.lstrip()
        else:
            current = candidate

    if current.strip():
        lines.append(current.strip())
    return lines


def _display_width(text: str) -> float:
    width = 0.0
    for char in text:
        if char.isspace():
            width += 0.45
        elif ord(char) < 128:
            width += 0.65
        else:
            width += 1.0
    return width


def _format_srt_time(ms: int) -> str:
    total_seconds, millis = divmod(max(0, ms), 1000)
    minutes_total, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes_total, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _escape_filter_path(path: Path) -> str:
    return path.as_posix().replace("\\", "\\\\").replace("'", "\\'")


def _fontfile_filter_options() -> list[str]:
    candidates = [
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return [f"fontfile='{_escape_filter_path(candidate)}'"]
    return []


def _segment_key(segment: VideoRenderSegment, fallback_index: int) -> str:
    return segment.segment_id or f"page_{segment.page_index}_{fallback_index}"


def _ensure_executable(name: str) -> None:
    if shutil.which(name) is None:
        raise PythonServiceException(f"{name} executable is not available")


def _run(command: list[str], label: str) -> None:
    logger.info("Video render command started. label=%s", label)
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        tail = ((completed.stderr or "") + "\n" + (completed.stdout or "")).strip()[-1200:]
        raise PythonServiceException(f"{label} failed: {tail}")
