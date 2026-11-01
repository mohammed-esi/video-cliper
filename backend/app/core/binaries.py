"""Startup checks for ffprobe/ffmpeg.

Both binaries must be available before the API starts: ffprobe validates
imports; ffmpeg is required for YouTube stream merges and the processing pipeline.
"""

import logging
import shutil
from pathlib import Path

from app.core.config import Settings

logger = logging.getLogger(__name__)


def _resolve_binary(path: str) -> Path | None:
    candidate = Path(path)
    if candidate.is_file():
        return candidate
    found = shutil.which(path)
    return Path(found) if found else None


def verify_media_binaries(settings: Settings) -> None:
    ffprobe = _resolve_binary(settings.ffprobe_path)
    if ffprobe is None:
        raise RuntimeError(
            "ffprobe was not found. Install FFmpeg and ensure ffprobe is on your PATH, "
            f"or set FFPROBE_PATH (currently {settings.ffprobe_path!r})."
        )

    ffmpeg = _resolve_binary(settings.ffmpeg_path)
    if ffmpeg is None:
        raise RuntimeError(
            "ffmpeg was not found. Install FFmpeg and ensure ffmpeg is on your PATH, "
            f"or set FFMPEG_PATH (currently {settings.ffmpeg_path!r})."
        )
