"""YouTube import error mapping and live extractor checks."""

import pytest
from yt_dlp.utils import DownloadError

from app.services.youtube_download import user_message_for_youtube_download_error


def test_page_reloaded_is_not_reported_as_sign_in() -> None:
    error = DownloadError("ERROR: [youtube] WhWc3b3KhnY: The page needs to be reloaded.")
    message = user_message_for_youtube_download_error(error)
    assert "signing in" not in message.lower()
    assert "automated access" in message.lower() or "yt-dlp" in message.lower()


def test_age_restricted_uses_sign_in_message() -> None:
    error = DownloadError("ERROR: Sign in to confirm your age")
    message = user_message_for_youtube_download_error(error)
    assert "signing in" in message.lower()


def test_private_video_message() -> None:
    error = DownloadError("ERROR: Private video. Sign in if you've been granted access.")
    message = user_message_for_youtube_download_error(error)
    assert "private" in message.lower()


def test_format_unavailable_message() -> None:
    error = DownloadError("ERROR: requested format is not available")
    message = user_message_for_youtube_download_error(error)
    assert "1080p" in message


@pytest.mark.network
def test_public_youtube_metadata_extracts() -> None:
    import yt_dlp

    url = "https://www.youtube.com/watch?v=WhWc3b3KhnY"
    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    assert isinstance(info, dict)
    assert info.get("id") == "WhWc3b3KhnY"
    assert (info.get("duration") or 0) > 0
