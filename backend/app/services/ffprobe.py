import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.errors import InvalidInputError, UnsupportedMediaError

logger = logging.getLogger(__name__)

_DISALLOWED_FORMAT_TOKENS = frozenset(
    {"hls", "mpegts", "concat", "image2", "dash", "rtp", "rtsp", "sdp"},
)
_ALLOWED_FORMAT_TOKENS = frozenset(
    {
        "mov",
        "mp4",
        "m4a",
        "3gp",
        "3g2",
        "mj2",
        "matroska",
        "webm",
        "avi",
        "flv",
    },
)


@dataclass(frozen=True, slots=True)
class ProbeResult:
    duration_seconds: float
    width: int
    height: int
    has_audio: bool
    container: str


def _parse_fraction(value: str) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            denominator = float(den)
            if denominator == 0:
                return None
            return float(num) / denominator
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def _rotation_degrees(stream: dict) -> int:
    tags = stream.get("tags") or {}
    rotate = tags.get("rotate")
    if rotate is None:
        return 0
    try:
        return int(float(rotate)) % 360
    except ValueError:
        return 0


def _pick_video_stream(streams: list[dict]) -> dict:
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    if not video_streams:
        raise UnsupportedMediaError("This file is not a supported video.")
    return video_streams[0]


def _validate_format_names(format_names: str) -> str:
    tokens = {part.strip().lower() for part in format_names.split(",") if part.strip()}
    if not tokens:
        raise UnsupportedMediaError("This file is not a supported video.")

    if tokens & _DISALLOWED_FORMAT_TOKENS:
        raise UnsupportedMediaError("This file is not a supported video.")

    if not tokens & _ALLOWED_FORMAT_TOKENS:
        raise UnsupportedMediaError("This file is not a supported video.")

    preferred = ("mp4", "mov", "matroska", "webm", "mkv", "m4v", "avi", "flv")
    for name in preferred:
        if name in tokens:
            return name
    return next(iter(tokens & _ALLOWED_FORMAT_TOKENS))


def parse_ffprobe_payload(payload: dict) -> ProbeResult:
    fmt = payload.get("format")
    if not isinstance(fmt, dict):
        raise UnsupportedMediaError("This file is not a supported video.")

    format_name = str(fmt.get("format_name") or "")
    container = _validate_format_names(format_name)

    streams = payload.get("streams")
    if not isinstance(streams, list):
        raise UnsupportedMediaError("This file is not a supported video.")

    video = _pick_video_stream(streams)
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    if width <= 0 or height <= 0:
        raise UnsupportedMediaError("This file is not a supported video.")

    rotation = _rotation_degrees(video)
    if rotation in {90, 270}:
        width, height = height, width

    duration_raw = fmt.get("duration")
    duration = float(duration_raw) if duration_raw is not None else None
    if duration is None or duration <= 0:
        duration = _parse_fraction(str(video.get("duration") or ""))
    if duration is None or duration <= 0:
        raise UnsupportedMediaError("This file is not a supported video.")

    has_audio = any(stream.get("codec_type") == "audio" for stream in streams)

    return ProbeResult(
        duration_seconds=duration,
        width=width,
        height=height,
        has_audio=has_audio,
        container=container,
    )


def run_ffprobe(path: Path, settings: Settings) -> ProbeResult:
    command = [
        settings.ffprobe_path,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=settings.ffprobe_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        logger.warning("ffprobe timed out for upload validation")
        raise InvalidInputError(
            "We couldn't read this video in time. Try a shorter clip or a different file."
        ) from exc

    if completed.returncode != 0:
        logger.debug("ffprobe failed with code %s", completed.returncode)
        raise UnsupportedMediaError("This file is not a supported video.")

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        logger.debug("ffprobe returned invalid JSON")
        raise UnsupportedMediaError("This file is not a supported video.") from exc

    return parse_ffprobe_payload(payload)


def enforce_probe_limits(result: ProbeResult, settings: Settings) -> None:
    if result.duration_seconds > settings.max_duration_seconds:
        raise InvalidInputError(
            "This video is too long. Choose a shorter file or trim it first."
        )
    if (
        result.width > settings.max_video_width
        or result.height > settings.max_video_height
    ):
        raise InvalidInputError(
            "This video exceeds the maximum supported resolution."
        )
