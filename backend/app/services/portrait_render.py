"""Render a 9:16 portrait MP4 from cached tracking data via FFmpeg sendcmd + crop.

OpenCV is not used here. The crop rectangle moves on a precomputed path; FFmpeg decodes,
crops, scales to 1080×1920, and re-encodes with audio from the same source segment.
"""

import json
import logging
import math
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.errors import InvalidInputError, MediaProcessingError
from app.schemas.tracking import CropGeometry, CropShot
from app.services.ffmpeg_runner import ffmpeg_input_argument, run_ffmpeg
from app.services.ffprobe import run_ffprobe
from app.services.tracking.analysis_cache import DETECTIONS_FILE
from app.services.tracking.crop_path import crop_x_at
from app.services.tracking.source_analysis import analyze_source, crop_path_for_range

logger = logging.getLogger(__name__)

PORTRAIT_WIDTH = 1080
PORTRAIT_HEIGHT = 1920
DEFAULT_SAMPLE_FPS = 25.0
TIME_EPSILON = 1e-6


@dataclass(frozen=True, slots=True)
class PortraitRenderResult:
    output_path: Path
    start_time: float
    end_time: float
    duration_seconds: float
    analysis_seconds: float
    render_seconds: float
    detection_cache_reused: bool
    sendcmd_path: Path | None


def portrait_output_size() -> tuple[int, int]:
    return PORTRAIT_WIDTH, PORTRAIT_HEIGHT


def source_video_fps(settings: Settings, source_path: Path) -> float:
    """Best-effort frame rate for sendcmd sampling (matches the source time base)."""
    command = [
        settings.ffprobe_path,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=r_frame_rate",
        "-of",
        "json",
        str(source_path.expanduser().resolve()),
    ]
    try:
        completed = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=30.0
        )
        streams = json.loads(completed.stdout).get("streams") or []
        if not streams:
            return DEFAULT_SAMPLE_FPS
        rate = streams[0].get("r_frame_rate", "")
        if "/" in rate:
            num, den = rate.split("/", 1)
            denominator = float(den)
            if denominator > 0:
                fps = float(num) / denominator
                if 1.0 <= fps <= 120.0:
                    return fps
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        logger.warning("Could not read source frame rate; using %.1f fps", DEFAULT_SAMPLE_FPS)
    return DEFAULT_SAMPLE_FPS


def sample_crop_events_for_sendcmd(
    shots: list[CropShot],
    geometry: CropGeometry,
    clip_start: float,
    clip_end: float,
    *,
    sample_fps: float,
) -> list[tuple[float, int]]:
    """Clip-local sendcmd times by sampling `crop_x_at` (linear between keyframes).

    FFmpeg sendcmd holds each crop position until the next command (zero-order hold).
    The cached crop path is defined with linear interpolation between keyframes, so we
    sample at video-frame times rather than exporting sparse analysis keyframes only.
    Positions are deduplicated when unchanged to limit camera motion when the subject
    already fits. Scene cuts stay sharp because `crop_x_at` never blends across shots.
    """
    duration = clip_end - clip_start
    if duration <= TIME_EPSILON:
        raise InvalidInputError("The clip range is outside the video.")
    if sample_fps <= 0:
        raise InvalidInputError("The clip range is outside the video.")

    interval = 1.0 / sample_fps
    events: list[tuple[float, int]] = []
    step_count = max(1, int(math.ceil(duration * sample_fps)))

    for step in range(step_count + 1):
        source_time = clip_start + step * interval
        if source_time > clip_end + TIME_EPSILON:
            source_time = clip_end
        local_time = round(source_time - clip_start, 6)
        x = crop_x_at(shots, geometry, source_time)
        if events and events[-1][1] == x:
            pass
        else:
            events.append((local_time, x))
        if source_time >= clip_end - TIME_EPSILON:
            break

    end_local = round(duration, 6)
    end_x = crop_x_at(shots, geometry, clip_end)
    if not events:
        events.append((0.0, end_x))
    elif events[-1][0] < end_local - TIME_EPSILON or events[-1][1] != end_x:
        if events[-1][0] == end_local:
            events[-1] = (end_local, end_x)
        else:
            events.append((end_local, end_x))
    return events


def build_sendcmd_content(events: list[tuple[float, int]], geometry: CropGeometry) -> str:
    """FFmpeg sendcmd text: comma-separated crop commands, semicolon-terminated lines."""
    if not events:
        raise InvalidInputError("The clip range is outside the video.")
    lines: list[str] = []
    width = geometry.crop_width
    height = geometry.crop_height
    y = geometry.crop_y
    for index, (local_time, x) in enumerate(events):
        if index == 0:
            lines.append(
                f"{local_time:.6f} crop w {width}, crop h {height}, crop x {x}, crop y {y};"
            )
        else:
            lines.append(f"{local_time:.6f} crop x {x};")
    return "\n".join(lines) + "\n"


def build_portrait_filter_graph(sendcmd_path: Path) -> str:
    """Video filter chain: dynamic crop then scale to exact 1080×1920."""
    path = sendcmd_path.expanduser().resolve().as_posix()
    # Colons in paths are rare on Unix; escape for libavfilter option parsing.
    escaped = path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return (
        f"[0:v]sendcmd=f='{escaped}',crop,"
        f"scale={PORTRAIT_WIDTH}:{PORTRAIT_HEIGHT}:flags=lanczos,"
        f"setsar=1,setdar=9/16[outv]"
    )


def build_portrait_ffmpeg_command(
    settings: Settings,
    *,
    source_path: Path,
    output_path: Path,
    sendcmd_path: Path,
    start_time: float,
    duration: float,
    has_audio: bool,
) -> list[str]:
    filter_graph = build_portrait_filter_graph(sendcmd_path)
    command = [
        settings.ffmpeg_path,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-protocol_whitelist",
        "file,pipe",
        "-ss",
        f"{start_time:.6f}",
        "-t",
        f"{duration:.6f}",
        "-i",
        ffmpeg_input_argument(source_path),
        "-filter_complex",
        filter_graph,
        "-map",
        "[outv]",
    ]
    if has_audio:
        command.extend(["-map", "0:a:0", "-c:a", "aac", "-b:a", "128k"])
    else:
        command.append("-an")
    command.extend(
        [
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    return command


def render_portrait_clip(
    settings: Settings,
    source_path: Path,
    analysis_dir: Path,
    *,
    start_time: float,
    end_time: float,
    output_path: Path,
) -> PortraitRenderResult:
    """Analyze (or reuse cache), plan the crop path for the range, and render one portrait MP4."""
    source_path = source_path.expanduser().resolve()
    probe = run_ffprobe(source_path, settings)
    duration = probe.duration_seconds
    if not 0.0 <= start_time < end_time <= duration + TIME_EPSILON:
        raise InvalidInputError("The clip range is outside the video.")

    detections_path = analysis_dir / DETECTIONS_FILE
    detections_mtime_before = (
        detections_path.stat().st_mtime_ns if detections_path.is_file() else None
    )

    analysis_started = time.monotonic()
    analysis = analyze_source(settings, source_path, analysis_dir)
    analysis_seconds = time.monotonic() - analysis_started
    detection_cache_reused = (
        detections_mtime_before is not None
        and detections_path.is_file()
        and detections_path.stat().st_mtime_ns == detections_mtime_before
    )

    shots = crop_path_for_range(analysis, start_time, end_time)
    geometry = analysis.crop_path.geometry
    sample_fps = source_video_fps(settings, source_path)
    events = sample_crop_events_for_sendcmd(
        shots, geometry, start_time, end_time, sample_fps=sample_fps
    )
    clip_duration = end_time - start_time

    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_name(f"{output_path.stem}.tmp.mp4")
    sendcmd_path = output_path.with_name(f".{output_path.stem}.sendcmd.txt")

    sendcmd_path.write_text(
        build_sendcmd_content(events, geometry), encoding="utf-8"
    )
    command = build_portrait_ffmpeg_command(
        settings,
        source_path=source_path,
        output_path=temp_output,
        sendcmd_path=sendcmd_path,
        start_time=start_time,
        duration=clip_duration,
        has_audio=probe.has_audio,
    )

    render_started = time.monotonic()
    try:
        run_ffmpeg(command, timeout_seconds=settings.ffmpeg_clip_timeout_seconds)
        if not temp_output.is_file() or temp_output.stat().st_size == 0:
            raise MediaProcessingError("We couldn't generate this clip. Please try again.")
        os.replace(temp_output, output_path)
    except Exception:
        temp_output.unlink(missing_ok=True)
        raise
    finally:
        sendcmd_path.unlink(missing_ok=True)

    render_seconds = time.monotonic() - render_started
    logger.info(
        "Portrait render start=%.3f end=%.3f cache_reused=%s analysis_s=%.1f render_s=%.1f",
        start_time,
        end_time,
        detection_cache_reused,
        analysis_seconds,
        render_seconds,
    )
    return PortraitRenderResult(
        output_path=output_path,
        start_time=start_time,
        end_time=end_time,
        duration_seconds=clip_duration,
        analysis_seconds=analysis_seconds,
        render_seconds=render_seconds,
        detection_cache_reused=detection_cache_reused,
        sendcmd_path=None,
    )
