from __future__ import annotations

import math
import re
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

from app.core.exceptions import PythonServiceException
from app.schemas.digital_human import (
    ActionFrame,
    AudioDriveGenerateRequest,
    AudioDriveGenerateResponse,
    AudioMetadata,
    PhonemeSegment,
    TokenTimelineItem,
)
from app.utils.logger import logger

# -----------------------------------------------------------------------------
# Vendor-neutral viseme map
# -----------------------------------------------------------------------------
# Most digital-human vendors accept a small, finite set of mouth shapes rather
# than raw phonetic symbols.  The map below intentionally keeps a stable neutral
# protocol that can be translated to a vendor-specific SDK by the Java rendering
# scheduler in task 36.  The left side is the internal phoneme label and the
# right side is the high-level mouth pose.
_PHONEME_TO_VISEME: dict[str, str] = {
    "sil": "REST",
    "a": "OPEN_A",
    "e": "WIDE_E",
    "i": "WIDE_I",
    "o": "ROUND_O",
    "u": "ROUND_U",
    "m": "CLOSED_M",
    "f": "TEETH_F",
    "s": "NARROW_S",
    "neutral": "NEUTRAL",
}

# Mouth coefficients are deliberately bounded in [0, 1] so the generated frames
# can be consumed directly by simple WebGL/SDK blend-shape drivers.
_VISEME_SHAPES: dict[str, tuple[float, float, float, float]] = {
    "REST": (0.02, 0.02, 0.05, 0.00),
    "OPEN_A": (0.88, 0.78, 0.18, 0.05),
    "WIDE_E": (0.48, 0.36, 0.82, 0.02),
    "WIDE_I": (0.34, 0.26, 0.92, 0.00),
    "ROUND_O": (0.62, 0.48, 0.10, 0.86),
    "ROUND_U": (0.44, 0.34, 0.05, 0.96),
    "CLOSED_M": (0.06, 0.04, 0.16, 0.04),
    "TEETH_F": (0.22, 0.10, 0.54, 0.02),
    "NARROW_S": (0.18, 0.10, 0.72, 0.00),
    "NEUTRAL": (0.20, 0.16, 0.22, 0.02),
}

_PUNCTUATION = set("，。！？；：,.!?;:")
_VOWEL_HINTS = {
    "a": "a",
    "e": "e",
    "i": "i",
    "o": "o",
    "u": "u",
    "v": "u",
}


@dataclass(frozen=True)
class _AudioSignal:
    duration_ms: int
    sample_rate: int | None
    channels: int | None
    samples: list[float]
    source: str
    warnings: list[str]


@dataclass(frozen=True)
class _Token:
    index: int
    text: str
    is_pause: bool
    weight: float


@dataclass(frozen=True)
class _FrameFeature:
    start_ms: int
    end_ms: int
    energy: float
    zcr: float


def generate_audio_drive_protocol(request: AudioDriveGenerateRequest) -> AudioDriveGenerateResponse:
    """Generate timeline, phoneme segments and avatar action frames.

    The service follows the three subtasks from I1-E:
    1. Extract coarse phoneme/viseme segments from the TTS audio waveform.
    2. Force-align lecture-script tokens to the audio duration at millisecond scale.
    3. Convert aligned phonemes to a vendor-neutral JSON/XML drive protocol.

    This implementation does not hard-code any third-party vendor contract.  It
    keeps a stable internal frame schema so task 36 can translate it to concrete
    SDK payloads without forcing the Python service to know vendor credentials.
    """

    signal = _load_audio_signal(request)
    tokens = _tokenize_script(request.script_text)
    if not tokens:
        raise PythonServiceException("讲稿文本未能切分出有效词元")

    frame_features = _extract_frame_features(signal, request.frame_interval_ms)
    token_timeline = _align_tokens_to_audio(tokens, signal.duration_ms)
    phoneme_segments = _build_phoneme_segments(tokens, token_timeline, frame_features, signal.source)
    action_frames = _build_action_frames(
        duration_ms=signal.duration_ms,
        frame_interval_ms=request.frame_interval_ms,
        phoneme_segments=phoneme_segments,
        tokens=token_timeline,
    )

    audio_metadata = AudioMetadata(
        durationMs=signal.duration_ms,
        sampleRate=signal.sample_rate,
        channels=signal.channels,
        source=signal.source,
    )
    protocol_json = _build_protocol_json(
        request=request,
        audio=audio_metadata,
        tokens=token_timeline,
        phonemes=phoneme_segments,
        frames=action_frames,
    )
    protocol_xml = _build_protocol_xml(protocol_json) if request.protocol_format in {"xml", "both"} else None

    logger.info(
        "Audio drive protocol generated. coursewareId=%s pageIndex=%s durationMs=%s tokens=%s frames=%s format=%s",
        request.courseware_id,
        request.page_index,
        signal.duration_ms,
        len(token_timeline),
        len(action_frames),
        request.protocol_format,
    )

    return AudioDriveGenerateResponse(
        coursewareId=request.courseware_id,
        pageIndex=request.page_index,
        audio=audio_metadata,
        tokens=token_timeline,
        phonemes=phoneme_segments,
        frames=action_frames,
        protocolJson=protocol_json if request.protocol_format in {"json", "both"} else None,
        protocolXml=protocol_xml,
        warnings=signal.warnings,
    )


def _load_audio_signal(request: AudioDriveGenerateRequest) -> _AudioSignal:
    """Load local WAV audio or use duration-only fallback.

    Only PCM WAV can be inspected with the Python standard library.  If another
    audio container is used during integration, Java should either convert it to
    WAV before calling this endpoint or pass ``audioDurationMs`` so the endpoint
    can still produce a deterministic protocol for early mock rendering.
    """

    warnings: list[str] = []
    if request.audio_path:
        audio_path = Path(request.audio_path).expanduser()
        if not audio_path.exists() or not audio_path.is_file():
            raise PythonServiceException(f"音频文件不存在：{audio_path}")
        try:
            return _read_pcm_wav(audio_path)
        except wave.Error as exc:
            if request.audio_duration_ms:
                warnings.append("audioPath 不是可读取的 PCM WAV，已使用 audioDurationMs 生成兜底时间轴")
                logger.warning("WAV parsing failed; duration fallback applied. path=%s reason=%s", audio_path, str(exc))
                return _duration_only_signal(request.audio_duration_ms, warnings)
            raise PythonServiceException("当前仅支持 PCM WAV 音频；如使用 mp3/pcm 请先转码或传入 audioDurationMs") from exc

    warnings.append("未提供 audioPath，已使用 audioDurationMs 生成文本驱动兜底时间轴")
    return _duration_only_signal(request.audio_duration_ms or 1, warnings)


def _read_pcm_wav(audio_path: Path) -> _AudioSignal:
    with wave.open(str(audio_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        frame_count = wav_file.getnframes()
        raw = wav_file.readframes(frame_count)

    if frame_count <= 0 or sample_rate <= 0:
        raise PythonServiceException("音频文件为空或采样率无效")

    duration_ms = max(1, round(frame_count * 1000 / sample_rate))
    samples = _decode_pcm_samples(raw, sample_width=sample_width, channels=channels)
    return _AudioSignal(
        duration_ms=duration_ms,
        sample_rate=sample_rate,
        channels=channels,
        samples=samples,
        source="wav",
        warnings=[],
    )


def _decode_pcm_samples(raw: bytes, sample_width: int, channels: int) -> list[float]:
    """Decode PCM bytes into mono float samples without optional dependencies.

    The decoder covers 8/16/24/32-bit PCM, which is sufficient for the WAV files
    produced by mainstream TTS engines.  Multi-channel audio is down-mixed by
    arithmetic averaging so mouth-motion features represent the audible speech.
    """

    if sample_width not in {1, 2, 3, 4}:
        raise PythonServiceException(f"不支持的 WAV 位宽：{sample_width * 8}bit")
    if channels <= 0:
        raise PythonServiceException("WAV 声道数无效")

    sample_count = len(raw) // sample_width
    channel_values: list[float] = []
    max_abs = float(2 ** (8 * sample_width - 1))

    for offset in range(0, sample_count * sample_width, sample_width):
        chunk = raw[offset : offset + sample_width]
        if sample_width == 1:
            # 8-bit PCM is unsigned in WAV.
            value = chunk[0] - 128
            normalized = value / 128.0
        else:
            # 16/24/32-bit PCM is little-endian signed integer.
            value = int.from_bytes(chunk, byteorder="little", signed=True)
            normalized = max(-1.0, min(1.0, value / max_abs))
        channel_values.append(normalized)

    mono_samples: list[float] = []
    for frame_start in range(0, len(channel_values), channels):
        frame = channel_values[frame_start : frame_start + channels]
        if frame:
            mono_samples.append(sum(frame) / len(frame))
    return mono_samples


def _duration_only_signal(duration_ms: int, warnings: list[str]) -> _AudioSignal:
    return _AudioSignal(
        duration_ms=max(1, duration_ms),
        sample_rate=None,
        channels=None,
        samples=[],
        source="duration-only",
        warnings=warnings,
    )


def _tokenize_script(script_text: str) -> list[_Token]:
    """Tokenize Chinese/English lecture text into alignable units.

    Chinese text is kept at character granularity because a stable word segmenter
    is not listed as a project dependency.  Consecutive English letters/digits are
    kept as one token.  Punctuation is retained as a short pause because it should
    create visible breathing and gesture boundaries in the digital-human protocol.
    """

    tokens: list[_Token] = []
    token_index = 0
    for match in re.finditer(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]|[^\s]", script_text):
        raw_token = match.group(0).strip()
        if not raw_token:
            continue
        is_pause = raw_token in _PUNCTUATION
        weight = _token_weight(raw_token, is_pause=is_pause)
        tokens.append(_Token(index=token_index, text=raw_token, is_pause=is_pause, weight=weight))
        token_index += 1
    return tokens


def _token_weight(token: str, *, is_pause: bool) -> float:
    if is_pause:
        return 0.35
    if re.fullmatch(r"[A-Za-z0-9_]+", token):
        return max(0.9, min(3.0, len(token) / 3.5))
    return 1.0


def _extract_frame_features(signal: _AudioSignal, frame_interval_ms: int) -> list[_FrameFeature]:
    if signal.source != "wav" or not signal.samples or not signal.sample_rate:
        return _synthetic_frame_features(signal.duration_ms, frame_interval_ms)

    samples_per_window = max(1, round(signal.sample_rate * frame_interval_ms / 1000))
    raw_features: list[tuple[int, int, float, float]] = []
    max_rms = 0.0

    for start in range(0, len(signal.samples), samples_per_window):
        window = signal.samples[start : start + samples_per_window]
        if not window:
            continue
        start_ms = round(start * 1000 / signal.sample_rate)
        end_ms = min(signal.duration_ms, round((start + len(window)) * 1000 / signal.sample_rate))
        rms = math.sqrt(sum(sample * sample for sample in window) / len(window))
        zcr = _zero_crossing_rate(window)
        raw_features.append((start_ms, max(start_ms + 1, end_ms), rms, zcr))
        max_rms = max(max_rms, rms)

    if not raw_features:
        return _synthetic_frame_features(signal.duration_ms, frame_interval_ms)

    denominator = max(max_rms, 1e-9)
    return [
        _FrameFeature(start_ms=start_ms, end_ms=end_ms, energy=min(1.0, rms / denominator), zcr=min(1.0, zcr))
        for start_ms, end_ms, rms, zcr in raw_features
    ]


def _zero_crossing_rate(samples: list[float]) -> float:
    if len(samples) <= 1:
        return 0.0
    crossings = 0
    previous = samples[0]
    for sample in samples[1:]:
        if (previous >= 0 > sample) or (previous < 0 <= sample):
            crossings += 1
        previous = sample
    return crossings / (len(samples) - 1)


def _synthetic_frame_features(duration_ms: int, frame_interval_ms: int) -> list[_FrameFeature]:
    features: list[_FrameFeature] = []
    for start_ms in range(0, duration_ms, frame_interval_ms):
        end_ms = min(duration_ms, start_ms + frame_interval_ms)
        # Smooth deterministic curve keeps text-only fallback visually alive but
        # avoids pretending to be precise audio analysis.
        phase = start_ms / max(duration_ms, 1)
        energy = 0.55 + 0.25 * math.sin(2 * math.pi * phase)
        features.append(_FrameFeature(start_ms=start_ms, end_ms=max(start_ms + 1, end_ms), energy=max(0.0, min(1.0, energy)), zcr=0.25))
    return features or [_FrameFeature(start_ms=0, end_ms=duration_ms, energy=0.5, zcr=0.25)]


def _align_tokens_to_audio(tokens: list[_Token], duration_ms: int) -> list[TokenTimelineItem]:
    total_weight = sum(token.weight for token in tokens)
    if total_weight <= 0:
        raise PythonServiceException("讲稿词元权重无效，无法生成时间轴")

    timeline: list[TokenTimelineItem] = []
    cursor = 0
    for position, token in enumerate(tokens):
        if position == len(tokens) - 1:
            end_ms = duration_ms
        else:
            raw_span = token.weight / total_weight * duration_ms
            min_span = 40 if token.is_pause else 80
            span_ms = max(min_span, round(raw_span))
            remaining_tokens = len(tokens) - position - 1
            remaining_min = remaining_tokens * 40
            end_ms = min(duration_ms - remaining_min, cursor + span_ms)
            end_ms = max(cursor + 1, end_ms)

        phoneme = _infer_token_phoneme(token.text, is_pause=token.is_pause)
        timeline.append(
            TokenTimelineItem(
                tokenIndex=token.index,
                token=token.text,
                startMs=cursor,
                endMs=max(cursor + 1, end_ms),
                phoneme=phoneme,
                viseme=_PHONEME_TO_VISEME.get(phoneme, "NEUTRAL"),
            )
        )
        cursor = max(cursor + 1, end_ms)

    return _normalize_timeline_bounds(timeline, duration_ms)


def _normalize_timeline_bounds(timeline: list[TokenTimelineItem], duration_ms: int) -> list[TokenTimelineItem]:
    normalized: list[TokenTimelineItem] = []
    cursor = 0
    for index, item in enumerate(timeline):
        end_ms = duration_ms if index == len(timeline) - 1 else min(duration_ms, max(cursor + 1, item.end_ms))
        normalized.append(
            TokenTimelineItem(
                tokenIndex=item.token_index,
                token=item.token,
                startMs=cursor,
                endMs=end_ms,
                phoneme=item.phoneme,
                viseme=item.viseme,
            )
        )
        cursor = end_ms
    return normalized


def _infer_token_phoneme(token: str, *, is_pause: bool) -> str:
    if is_pause:
        return "sil"

    lowered = token.lower()
    if re.fullmatch(r"[A-Za-z0-9_]+", token):
        for char in lowered:
            if char in _VOWEL_HINTS:
                return _VOWEL_HINTS[char]
        if any(char in lowered for char in "mbp"):
            return "m"
        if any(char in lowered for char in "fv"):
            return "f"
        if any(char in lowered for char in "szcx"):
            return "s"
        return "neutral"

    # Chinese characters do not expose pronunciation without a pinyin or ASR/MFA
    # dependency.  The deterministic bucket keeps repeated requests stable and is
    # later refined by waveform energy when action frames are built.
    bucket = ord(token[0]) % 7
    return ["a", "e", "i", "o", "u", "m", "s"][bucket]


def _build_phoneme_segments(
    tokens: list[_Token],
    token_timeline: list[TokenTimelineItem],
    frame_features: list[_FrameFeature],
    source: str,
) -> list[PhonemeSegment]:
    segments: list[PhonemeSegment] = []
    for token, timeline_item in zip(tokens, token_timeline, strict=False):
        energy = _average_energy(frame_features, timeline_item.start_ms, timeline_item.end_ms)
        phoneme = timeline_item.phoneme
        if not token.is_pause and source == "wav":
            phoneme = _refine_phoneme_by_audio(phoneme, energy=energy, zcr=_average_zcr(frame_features, timeline_item.start_ms, timeline_item.end_ms))
        confidence = 0.82 if source == "wav" else 0.58
        if token.is_pause:
            confidence = 0.95
        segments.append(
            PhonemeSegment(
                startMs=timeline_item.start_ms,
                endMs=timeline_item.end_ms,
                phoneme=phoneme,
                viseme=_PHONEME_TO_VISEME.get(phoneme, "NEUTRAL"),
                energy=round(energy, 4),
                confidence=confidence,
            )
        )
    return _merge_adjacent_segments(segments)


def _average_energy(features: list[_FrameFeature], start_ms: int, end_ms: int) -> float:
    values = [feature.energy for feature in features if feature.end_ms > start_ms and feature.start_ms < end_ms]
    if not values:
        return 0.0
    return max(0.0, min(1.0, sum(values) / len(values)))


def _average_zcr(features: list[_FrameFeature], start_ms: int, end_ms: int) -> float:
    values = [feature.zcr for feature in features if feature.end_ms > start_ms and feature.start_ms < end_ms]
    if not values:
        return 0.0
    return max(0.0, min(1.0, sum(values) / len(values)))


def _refine_phoneme_by_audio(phoneme: str, *, energy: float, zcr: float) -> str:
    if energy < 0.08:
        return "sil"
    if phoneme in {"m", "f", "s"}:
        return phoneme
    if zcr > 0.38:
        return "s"
    if energy > 0.78 and phoneme in {"a", "e", "i", "o", "u", "neutral"}:
        return "a"
    return phoneme


def _merge_adjacent_segments(segments: list[PhonemeSegment]) -> list[PhonemeSegment]:
    merged: list[PhonemeSegment] = []
    for segment in segments:
        if not merged:
            merged.append(segment)
            continue
        previous = merged[-1]
        if previous.phoneme == segment.phoneme and previous.viseme == segment.viseme:
            total_span = max(1, segment.end_ms - previous.start_ms)
            previous_span = previous.end_ms - previous.start_ms
            segment_span = segment.end_ms - segment.start_ms
            weighted_energy = (previous.energy * previous_span + segment.energy * segment_span) / total_span
            weighted_confidence = (previous.confidence * previous_span + segment.confidence * segment_span) / total_span
            merged[-1] = PhonemeSegment(
                startMs=previous.start_ms,
                endMs=segment.end_ms,
                phoneme=previous.phoneme,
                viseme=previous.viseme,
                energy=round(weighted_energy, 4),
                confidence=round(weighted_confidence, 4),
            )
        else:
            merged.append(segment)
    return merged


def _build_action_frames(
    *,
    duration_ms: int,
    frame_interval_ms: int,
    phoneme_segments: list[PhonemeSegment],
    tokens: list[TokenTimelineItem],
) -> list[ActionFrame]:
    frames: list[ActionFrame] = []
    for time_ms in range(0, duration_ms + 1, frame_interval_ms):
        segment = _find_active_segment(phoneme_segments, time_ms)
        viseme = segment.viseme if segment else "REST"
        phoneme = segment.phoneme if segment else "sil"
        energy = segment.energy if segment else 0.0
        mouth_open, jaw_open, lip_wide, lip_round = _apply_energy_to_shape(viseme, energy)
        eye_blink = _blink_value(time_ms)
        head_pitch, head_yaw = _head_motion(time_ms, duration_ms)
        gesture = _gesture_at_time(time_ms, tokens, phoneme)
        frames.append(
            ActionFrame(
                timeMs=time_ms,
                phoneme=phoneme,
                viseme=viseme,
                mouthOpen=mouth_open,
                jawOpen=jaw_open,
                lipWide=lip_wide,
                lipRound=lip_round,
                eyeBlink=eye_blink,
                headPitch=head_pitch,
                headYaw=head_yaw,
                gesture=gesture,
            )
        )
    return frames


def _find_active_segment(segments: list[PhonemeSegment], time_ms: int) -> PhonemeSegment | None:
    for segment in segments:
        if segment.start_ms <= time_ms < segment.end_ms:
            return segment
    if segments and time_ms >= segments[-1].end_ms:
        return segments[-1]
    return None


def _apply_energy_to_shape(viseme: str, energy: float) -> tuple[float, float, float, float]:
    mouth_open, jaw_open, lip_wide, lip_round = _VISEME_SHAPES.get(viseme, _VISEME_SHAPES["NEUTRAL"])
    # Energy affects articulation amplitude, but consonants should not disappear
    # completely at quiet waveform sections.
    scale = 0.45 + 0.55 * max(0.0, min(1.0, energy))
    return (
        round(min(1.0, mouth_open * scale), 4),
        round(min(1.0, jaw_open * scale), 4),
        round(min(1.0, lip_wide * (0.75 + 0.25 * scale)), 4),
        round(min(1.0, lip_round * (0.75 + 0.25 * scale)), 4),
    )


def _blink_value(time_ms: int) -> float:
    # A deterministic blink every 3.2 seconds, with a short 160ms envelope.
    cycle = time_ms % 3200
    if 80 <= cycle <= 160:
        return 1.0
    if 40 <= cycle < 80 or 160 < cycle <= 200:
        return 0.45
    return 0.0


def _head_motion(time_ms: int, duration_ms: int) -> tuple[float, float]:
    if duration_ms <= 0:
        return 0.0, 0.0
    seconds = time_ms / 1000.0
    pitch = 0.10 * math.sin(seconds * 1.35)
    yaw = 0.08 * math.sin(seconds * 0.82 + 0.7)
    return round(pitch, 4), round(yaw, 4)


def _gesture_at_time(time_ms: int, tokens: list[TokenTimelineItem], phoneme: str) -> str:
    if phoneme == "sil":
        return "pause"
    token = _find_active_token(tokens, time_ms)
    if token and token.token in {"！", "?", "？", "!"}:
        return "emphasis"
    if token and token.start_ms == time_ms:
        return "beat"
    return "idle"


def _find_active_token(tokens: list[TokenTimelineItem], time_ms: int) -> TokenTimelineItem | None:
    for token in tokens:
        if token.start_ms <= time_ms < token.end_ms:
            return token
    return None


def _build_protocol_json(
    *,
    request: AudioDriveGenerateRequest,
    audio: AudioMetadata,
    tokens: list[TokenTimelineItem],
    phonemes: list[PhonemeSegment],
    frames: list[ActionFrame],
) -> dict:
    return {
        "version": request.sdk_version,
        "avatarId": request.avatar_id,
        "coursewareId": request.courseware_id,
        "pageIndex": request.page_index,
        "audio": {
            "url": request.audio_url,
            "path": request.audio_path,
            "durationMs": audio.duration_ms,
            "sampleRate": audio.sample_rate,
            "channels": audio.channels,
            "source": audio.source,
        },
        "timeline": [item.model_dump(by_alias=True) for item in tokens],
        "phonemes": [item.model_dump(by_alias=True) for item in phonemes],
        "frames": [item.model_dump(by_alias=True) for item in frames],
    }


def _build_protocol_xml(protocol_json: dict) -> str:
    root = ET.Element("DigitalHumanDrive", attrib={"version": str(protocol_json.get("version") or "")})
    ET.SubElement(root, "AvatarId").text = str(protocol_json.get("avatarId") or "")
    ET.SubElement(root, "CoursewareId").text = str(protocol_json.get("coursewareId") or "")
    if protocol_json.get("pageIndex") is not None:
        ET.SubElement(root, "PageIndex").text = str(protocol_json.get("pageIndex"))

    audio_element = ET.SubElement(root, "Audio")
    for key, value in (protocol_json.get("audio") or {}).items():
        if value is not None:
            ET.SubElement(audio_element, key).text = str(value)

    timeline_element = ET.SubElement(root, "Timeline")
    _append_items(timeline_element, "Token", protocol_json.get("timeline") or [])

    phonemes_element = ET.SubElement(root, "Phonemes")
    _append_items(phonemes_element, "Phoneme", protocol_json.get("phonemes") or [])

    frames_element = ET.SubElement(root, "Frames")
    _append_items(frames_element, "Frame", protocol_json.get("frames") or [])

    return ET.tostring(root, encoding="unicode", short_empty_elements=True)


def _append_items(parent: ET.Element, item_name: str, items: Iterable[dict]) -> None:
    for item in items:
        element = ET.SubElement(parent, item_name)
        for key, value in item.items():
            if value is None:
                continue
            child = ET.SubElement(element, key)
            child.text = str(value)
