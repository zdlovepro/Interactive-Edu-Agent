from __future__ import annotations

import json
import math
import shutil
import subprocess
import textwrap
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from app.core.config import settings
from app.core.exceptions import AppException, BUSINESS_VALIDATION_FAILED, PythonServiceException
from app.schemas.video_render import (
    VideoRenderRequest,
    VideoRenderResult,
    VideoRenderSegment,
    VideoRenderTimelineItem,
)
from app.utils.logger import logger


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

    timeline: list[VideoRenderTimelineItem] = []
    part_paths: list[Path] = []
    cursor_ms = 0

    for index, segment in enumerate(sorted(request.segments, key=lambda item: item.page_index), start=1):
        image_path = _resolve_existing_file(segment.page_image_path, "page image")
        audio_path = _resolve_or_create_audio(segment, audio_dir, request.backend_base_url)
        duration_ms = segment.duration_ms or _probe_audio_duration_ms(audio_path)
        if duration_ms <= 0:
            duration_ms = _estimate_duration_ms(segment.script_text)

        part_path = part_dir / f"part_{index:03d}.mp4"
        subtitle_text_path = input_dir / f"subtitle_{index:03d}.txt"
        subtitle_text_path.write_text(_subtitle_text(segment), encoding="utf-8")

        _render_part(
            image_path=image_path,
            audio_path=audio_path,
            subtitle_text_path=subtitle_text_path,
            output_path=part_path,
            width=request.width,
            height=request.height,
        )
        part_paths.append(part_path)

        end_ms = cursor_ms + duration_ms
        timeline.append(
            VideoRenderTimelineItem(
                segmentId=segment.segment_id or f"seg_{index:03d}",
                pageIndex=segment.page_index,
                title=segment.title,
                startMs=cursor_ms,
                endMs=end_ms,
                durationMs=duration_ms,
                pageImagePath=str(image_path),
                audioPath=str(audio_path),
            )
        )
        cursor_ms = end_ms

    timeline_path = output_dir / "timeline.json"
    timeline_path.write_text(
        json.dumps([item.model_dump(by_alias=True) for item in timeline], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    subtitle_path = output_dir / "subtitles.srt"
    subtitle_path.write_text(_build_srt(timeline, request.segments), encoding="utf-8")

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
        "Courseware video render finished. coursewareId=%s segments=%s durationMs=%s mp4=%s",
        request.courseware_id,
        len(timeline),
        cursor_ms,
        mp4_path,
    )
    return result.model_dump(by_alias=True)


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

    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise AppException(BUSINESS_VALIDATION_FAILED, f"unsupported audioUrl scheme: {parsed.scheme}")

    suffix = Path(parsed.path).suffix or ".audio"
    target = target.with_suffix(suffix)
    try:
        with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - URL comes from trusted backend state.
            target.write_bytes(response.read())
    except Exception as exc:  # noqa: BLE001
        raise PythonServiceException(f"failed to download segment audio: {parsed.netloc}") from exc

    if target.stat().st_size <= 0:
        raise PythonServiceException("downloaded segment audio is empty")
    return target


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
    subtitle_text_path: Path,
    output_path: Path,
    width: int,
    height: int,
) -> None:
    drawtext_options = [
        *_fontfile_filter_options(),
        "fontcolor=white",
        "fontsize=30",
        "box=1",
        "boxcolor=black@0.58",
        "boxborderw=18",
        "x=(w-text_w)/2",
        "y=h-text_h-52",
        f"textfile='{_escape_filter_path(subtitle_text_path)}'",
    ]
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"drawtext={':'.join(drawtext_options)}"
    )
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
        "-vf",
        vf,
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
    _run(command, f"render video part {output_path.name}")


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
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
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
    # Rough Mandarin narration estimate: about 4 chars/sec, bounded for demo usability.
    seconds = min(30, max(4, math.ceil(length / 4)))
    return seconds * 1000


def _subtitle_text(segment: VideoRenderSegment) -> str:
    text = " ".join((segment.script_text or segment.title or f"Page {segment.page_index}").split())
    if not text:
        return f"Page {segment.page_index}"
    lines = textwrap.wrap(text, width=30, break_long_words=True, replace_whitespace=False)
    return "\n".join(lines[:2])


def _build_srt(timeline: list[VideoRenderTimelineItem], segments: list[VideoRenderSegment]) -> str:
    segments_by_page = {item.page_index: item for item in segments}
    blocks: list[str] = []
    for index, item in enumerate(timeline, start=1):
        segment = segments_by_page.get(item.page_index)
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{_format_srt_time(item.start_ms)} --> {_format_srt_time(item.end_ms)}",
                    _subtitle_text(segment) if segment else item.title or f"Page {item.page_index}",
                    "",
                ]
            )
        )
    return "\n".join(blocks)


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


def _ensure_executable(name: str) -> None:
    if shutil.which(name) is None:
        raise PythonServiceException(f"{name} executable is not available")


def _run(command: list[str], label: str) -> None:
    logger.info("Video render command started. label=%s", label)
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        tail = ((completed.stderr or "") + "\n" + (completed.stdout or "")).strip()[-1200:]
        raise PythonServiceException(f"{label} failed: {tail}")
