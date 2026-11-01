import re

import pytest

from app.core.errors import InvalidInputError
from app.services.youtube_download import (
    _MAX_IMPORT_HEIGHT,
    _reject_if_resolution_too_high,
    _user_message_for_download_error,
    youtube_download_format_selector,
)
from yt_dlp.utils import DownloadError


def test_format_selector_caps_height_and_avoids_unbounded_best() -> None:
    selector = youtube_download_format_selector()
    assert f"[height<={_MAX_IMPORT_HEIGHT}]" in selector
    assert "bestvideo+bestaudio" not in selector
    assert not re.search(r"/best(?!.*height)", selector)
    assert "+ba" in selector
    assert "ext=mp4" in selector
    assert "acodec!=none" in selector


def test_format_unavailable_error_message() -> None:
    message = _user_message_for_download_error(
        DownloadError("Requested format is not available")
    )
    assert "1080p or below" in message


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (1920, 1080),
        (1280, 720),
        (640, 360),
        (1080, 1920),  # portrait / Shorts
        (720, 1280),
        (608, 1080),
    ],
)
def test_accepts_at_or_below_1080p(width: int, height: int) -> None:
    _reject_if_resolution_too_high(width, height)


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (3840, 2160),
        (2560, 1440),
        (2160, 3840),  # portrait 4K Short
        (1080, 1921),
    ],
)
def test_rejects_above_1080p(width: int, height: int) -> None:
    with pytest.raises(InvalidInputError, match="1080p"):
        _reject_if_resolution_too_high(width, height)


def test_ffmpeg_missing_error_message_for_merge() -> None:
    message = _user_message_for_download_error(
        DownloadError(
            "ERROR: ffmpeg not found. Please install or provide path using "
            "--ffmpeg-location"
        )
    )
    assert "FFmpeg" in message
    assert "combine video and audio" in message
