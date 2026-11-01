from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.core.errors import ImportInProgressError, InvalidInputError, PayloadTooLargeError
from app.schemas.video import VideoUploadResponse
from app.services.import_lock import media_import_lock
from yt_dlp.utils import DownloadError

from app.services.youtube_download import import_youtube_video
from app.services.youtube_urls import ParsedYoutubeUrl


@pytest.fixture
def parsed_url() -> ParsedYoutubeUrl:
    return ParsedYoutubeUrl(
        video_id="dQw4w9WgXcQ",
        canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )


def test_rejects_when_metadata_duration_exceeds_limit(
    parsed_url: ParsedYoutubeUrl,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()
    settings = settings.model_copy(update={"max_duration_seconds": 10})

    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = {"duration": 60, "filesize": 1000}
    mock_ydl.__enter__.return_value = mock_ydl

    with patch("app.services.youtube_download.yt_dlp.YoutubeDL", return_value=mock_ydl):
        with pytest.raises(InvalidInputError, match="too long"):
            import_youtube_video(parsed_url, settings)

    get_settings.cache_clear()


def test_rejects_when_metadata_size_exceeds_limit(
    parsed_url: ParsedYoutubeUrl,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()
    settings = settings.model_copy(update={"max_upload_bytes": 1000})

    mock_ydl = MagicMock()
    mock_ydl.extract_info.return_value = {"duration": 5, "filesize": 5000}
    mock_ydl.__enter__.return_value = mock_ydl

    with patch("app.services.youtube_download.yt_dlp.YoutubeDL", return_value=mock_ydl):
        with pytest.raises(PayloadTooLargeError):
            import_youtube_video(parsed_url, settings)

    get_settings.cache_clear()


def test_ffmpeg_missing_during_merge_returns_clear_error(
    parsed_url: ParsedYoutubeUrl,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()

    probe_ydl = MagicMock()
    probe_ydl.extract_info.return_value = {"duration": 5, "filesize": 1000}
    probe_ydl.__enter__.return_value = probe_ydl

    download_ydl = MagicMock()
    download_ydl.download.side_effect = DownloadError(
        "ERROR: ffmpeg not found. Please install or provide path using "
        "--ffmpeg-location"
    )
    download_ydl.__enter__.return_value = download_ydl

    with patch(
        "app.services.youtube_download.yt_dlp.YoutubeDL",
        side_effect=[probe_ydl, download_ydl],
    ):
        with pytest.raises(InvalidInputError, match="FFmpeg"):
            import_youtube_video(parsed_url, settings)

    get_settings.cache_clear()


def test_cleanup_after_download_failure(
    parsed_url: ParsedYoutubeUrl,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()

    probe_ydl = MagicMock()
    probe_ydl.extract_info.return_value = {"duration": 5, "filesize": 1000}
    probe_ydl.__enter__.return_value = probe_ydl

    download_ydl = MagicMock()
    download_ydl.download.side_effect = RuntimeError("network down")
    download_ydl.__enter__.return_value = download_ydl

    with patch(
        "app.services.youtube_download.yt_dlp.YoutubeDL",
        side_effect=[probe_ydl, download_ydl],
    ):
        with pytest.raises(InvalidInputError):
            import_youtube_video(parsed_url, settings)

    assert not (tmp_path / "jobs").exists() or not any((tmp_path / "jobs").iterdir())
    get_settings.cache_clear()


def test_concurrent_import_returns_clear_error(
    parsed_url: ParsedYoutubeUrl,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()

    with media_import_lock():
        with pytest.raises(ImportInProgressError):
            import_youtube_video(parsed_url, settings)

    get_settings.cache_clear()


def test_accepts_download_without_audio_track(
    parsed_url: ParsedYoutubeUrl,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()

    probe_ydl = MagicMock()
    probe_ydl.extract_info.return_value = {"duration": 5, "filesize": 1000}
    probe_ydl.__enter__.return_value = probe_ydl

    download_ydl = MagicMock()
    download_ydl.__enter__.return_value = download_ydl

    def _create_download_file(*_args, **_kwargs) -> None:
        jobs = tmp_path / "jobs"
        job_dirs = list(jobs.iterdir()) if jobs.exists() else []
        assert job_dirs
        target = job_dirs[0] / "download.mp4"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"\x00" * 128)

    download_ydl.download.side_effect = _create_download_file

    silent_response = VideoUploadResponse(
        video_id=uuid4(),
        original_filename="youtube-dQw4w9WgXcQ.mp4",
        duration_seconds=5.0,
        width=640,
        height=360,
        has_audio=False,
        container="mp4",
    )

    with patch(
        "app.services.youtube_download.yt_dlp.YoutubeDL",
        side_effect=[probe_ydl, download_ydl],
    ):
        with patch(
            "app.services.youtube_download.finalize_uploaded_video",
            return_value=silent_response,
        ) as finalize_mock:
            result = import_youtube_video(parsed_url, settings)
            finalize_mock.assert_called_once()
            assert result.has_audio is False

    get_settings.cache_clear()


def test_successful_import_uses_ffprobe_finalize(
    parsed_url: ParsedYoutubeUrl,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()

    probe_ydl = MagicMock()
    probe_ydl.extract_info.return_value = {"duration": 5, "filesize": 1000}
    probe_ydl.__enter__.return_value = probe_ydl

    download_ydl = MagicMock()
    download_ydl.download.return_value = None
    download_ydl.__enter__.return_value = download_ydl

    fake_probe_response = VideoUploadResponse(
        video_id=uuid4(),
        original_filename="youtube-dQw4w9WgXcQ.mp4",
        duration_seconds=5.0,
        width=640,
        height=360,
        has_audio=True,
        container="mp4",
    )

    def _create_download_file(*_args, **_kwargs) -> None:
        jobs = tmp_path / "jobs"
        job_dirs = list(jobs.iterdir()) if jobs.exists() else []
        assert job_dirs
        target = job_dirs[0] / "download.mp4"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"\x00" * 128)

    download_ydl.download.side_effect = _create_download_file

    with patch(
        "app.services.youtube_download.yt_dlp.YoutubeDL",
        side_effect=[probe_ydl, download_ydl],
    ):
        with patch(
            "app.services.youtube_download.finalize_uploaded_video",
            return_value=fake_probe_response,
        ) as finalize_mock:
            result = import_youtube_video(parsed_url, settings)
            finalize_mock.assert_called_once()
            assert result.original_filename == fake_probe_response.original_filename

    get_settings.cache_clear()
