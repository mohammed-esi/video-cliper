import logging
import re
import uuid
from concurrent import futures
from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError

from app.core.config import Settings
from app.core.errors import AppError, InvalidInputError, PayloadTooLargeError
from app.core.paths import job_dir, resolve_data_dir
from app.schemas.video import VideoUploadResponse
from app.services.import_lock import media_import_lock
from app.services.video_upload import finalize_uploaded_video, remove_job_tree
from app.services.youtube_urls import ParsedYoutubeUrl

logger = logging.getLogger(__name__)

# YouTube download cap (local uploads use Settings.max_video_* instead).
# Later pipeline stages may normalize to a working resolution for processing.
_MAX_IMPORT_HEIGHT = 1080


def youtube_download_format_selector() -> str:
    """yt-dlp format string: <=1080p, MP4-friendly, merged A/V, no 4K fallback."""
    h = _MAX_IMPORT_HEIGHT
    return (
        f"bv*[ext=mp4][height<={h}][vcodec^=avc1]+ba[ext=m4a]/"
        f"bv*[ext=mp4][height<={h}]+ba[ext=m4a]/"
        f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/"
        f"bv*[height<={h}]+ba[ext=m4a]/"
        f"bv*[height<={h}]+ba/"
        f"b[height<={h}][ext=mp4][acodec!=none]/"
        f"b[height<={h}][acodec!=none]"
    )


def _estimated_size_bytes(info: dict[str, Any]) -> int | None:
    for key in ("filesize", "filesize_approx"):
        value = info.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return None


_AGE_RESTRICTED = re.compile(
    r"age[- ]restricted|confirm your age|inappropriate for some users",
    re.IGNORECASE,
)
_SIGN_IN_REQUIRED = re.compile(
    r"sign in to (?:view|watch|confirm)|login required|members.only|"
    r"authentication required|cookies.*sign in",
    re.IGNORECASE,
)
_BOT_OR_EXTRACTOR = re.compile(
    r"page needs to be reloaded|confirm you.?re not a bot|"
    r"unable to extract (?:player )?data|http error 403|"
    r"this helps protect our community",
    re.IGNORECASE,
)
_UNAVAILABLE = re.compile(
    r"video (?:is )?unavailable|this video is not available|"
    r"has been removed|private video",
    re.IGNORECASE,
)


def user_message_for_youtube_download_error(error: Exception) -> str:
    """Map yt-dlp failures to plain-language import errors (also used in tests)."""
    text = str(error)
    lowered = text.lower()
    if _UNAVAILABLE.search(text) or (
        "unavailable" in lowered and "reloaded" not in lowered
    ):
        if "private" in lowered:
            return "This video is private. Try a public link instead."
        return "This video isn't available. Check the link and try again."
    if "format is not available" in lowered or "requested format" in lowered:
        return (
            "This video has no downloadable format at 1080p or below. "
            "Try another link or upload a file instead."
        )
    if _AGE_RESTRICTED.search(text) or _SIGN_IN_REQUIRED.search(text):
        return "This video can't be imported without signing in. Use a public video."
    if _BOT_OR_EXTRACTOR.search(text):
        return (
            "YouTube blocked automated access to this video. Try again later, "
            "update yt-dlp, or upload the file instead."
        )
    if "copyright" in lowered or "blocked in your country" in lowered:
        return "This video can't be downloaded due to restrictions."
    if "ffmpeg" in lowered and (
        "not found" in lowered or "not installed" in lowered or "postprocessing" in lowered
    ):
        return (
            "YouTube import needs FFmpeg to combine video and audio. Install FFmpeg "
            "and ensure ffmpeg is on your PATH, or set FFMPEG_PATH."
        )
    if "timed out" in lowered or "timeout" in lowered or "connection" in lowered:
        return (
            "We couldn't reach YouTube. Check your connection and try again."
        )
    return "We couldn't import this YouTube video. Try another link."


def _user_message_for_download_error(error: Exception) -> str:
    return user_message_for_youtube_download_error(error)


def _reject_if_resolution_too_high(width: int, height: int) -> None:
    if min(width, height) > _MAX_IMPORT_HEIGHT or max(width, height) > 1920:
        raise InvalidInputError(
            "Downloaded video exceeds 1080p. Try another link or upload a file instead."
        )


def _build_youtube_dl_options(
    *,
    job_directory: Path,
    max_bytes: int,
    timeout_seconds: float,
    size_state: dict[str, int | bool],
) -> dict[str, Any]:
    outtmpl = str(job_directory / "download.%(ext)s")

    def progress_hook(status: dict[str, Any]) -> None:
        if status.get("status") != "downloading":
            return
        downloaded = int(status.get("downloaded_bytes") or 0)
        size_state["downloaded"] = downloaded
        if downloaded > max_bytes:
            size_state["limit_exceeded"] = True
            raise DownloadError("Download exceeded the size limit.")

    return {
        "allowed_extractors": ["youtube"],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": min(timeout_seconds, 30.0),
        "retries": 1,
        "fragment_retries": 1,
        "max_filesize": max_bytes,
        "outtmpl": outtmpl,
        "format": youtube_download_format_selector(),
        "merge_output_format": "mp4",
        "progress_hooks": [progress_hook],
    }


def _run_timed_download(
    *,
    canonical_url: str,
    options: dict[str, Any],
    timeout_seconds: float,
) -> None:
    def _download() -> None:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([canonical_url])

    with futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_download)
        try:
            future.result(timeout=timeout_seconds)
        except futures.TimeoutError as exc:
            raise InvalidInputError(
                "This download took too long. Try a shorter video or upload a file instead."
            ) from exc


def _find_downloaded_file(job_directory: Path) -> Path:
    candidates = sorted(
        path
        for path in job_directory.iterdir()
        if path.is_file() and path.name.startswith("download.")
    )
    if not candidates:
        raise InvalidInputError("We couldn't import this YouTube video. Try another link.")
    return candidates[0]


def _cleanup_partial_files(job_directory: Path) -> None:
    if not job_directory.is_dir():
        return
    for leftover in job_directory.glob("download.*"):
        leftover.unlink(missing_ok=True)
    has_source = any(path.name.startswith("source.") for path in job_directory.iterdir())
    if not has_source:
        remove_job_tree(job_directory)


def import_youtube_video(
    parsed: ParsedYoutubeUrl,
    settings: Settings,
) -> VideoUploadResponse:
    video_id = uuid.uuid4()
    directory = job_dir(settings.data_dir, video_id)
    resolve_data_dir(settings.data_dir).mkdir(parents=True, exist_ok=True)
    directory.mkdir(parents=True, exist_ok=True)

    display_name = f"youtube-{parsed.video_id}.mp4"
    size_state: dict[str, int | bool] = {"downloaded": 0, "limit_exceeded": False}

    with media_import_lock():
        try:
            probe_options = _build_youtube_dl_options(
                job_directory=directory,
                max_bytes=settings.max_upload_bytes,
                timeout_seconds=settings.youtube_download_timeout_seconds,
                size_state=size_state,
            )

            with yt_dlp.YoutubeDL({**probe_options, "skip_download": True}) as ydl:
                info = ydl.extract_info(parsed.canonical_url, download=False)

            if not isinstance(info, dict):
                raise InvalidInputError("We couldn't read this YouTube video.")

            duration = info.get("duration")
            if isinstance(duration, (int, float)) and duration > 0:
                if float(duration) > settings.max_duration_seconds:
                    raise InvalidInputError(
                        "This video is too long. Choose a shorter video or trim it first."
                    )

            estimated_size = _estimated_size_bytes(info)
            if estimated_size is not None and estimated_size > settings.max_upload_bytes:
                raise PayloadTooLargeError(
                    "This video is too large. Choose a smaller video or upload a file instead."
                )

            _run_timed_download(
                canonical_url=parsed.canonical_url,
                options=probe_options,
                timeout_seconds=settings.youtube_download_timeout_seconds,
            )

            if size_state.get("limit_exceeded"):
                raise PayloadTooLargeError(
                    "This video is too large. Choose a smaller video or upload a file instead."
                )

            downloaded_path = _find_downloaded_file(directory)
            if downloaded_path.stat().st_size > settings.max_upload_bytes:
                raise PayloadTooLargeError(
                    "This video is too large. Choose a smaller video or upload a file instead."
                )

            stored_path = directory / f"source{downloaded_path.suffix.lower() or '.mp4'}"
            downloaded_path.replace(stored_path)

            logger.info("Imported YouTube video_id=%s yt_id=%s", video_id, parsed.video_id)
            response = finalize_uploaded_video(
                video_id=video_id,
                stored_path=stored_path,
                original_filename=display_name,
                settings=settings,
            )
            try:
                _reject_if_resolution_too_high(response.width, response.height)
            except InvalidInputError:
                remove_job_tree(directory)
                raise
            return response
        except AppError:
            _cleanup_partial_files(directory)
            raise
        except DownloadError as exc:
            logger.info(
                "YouTube download failed yt_id=%s detail=%s",
                parsed.video_id,
                exc,
            )
            _cleanup_partial_files(directory)
            if size_state.get("limit_exceeded"):
                raise PayloadTooLargeError(
                    "This video is too large. Choose a smaller video or upload a file instead."
                ) from exc
            raise InvalidInputError(_user_message_for_download_error(exc)) from exc
        except Exception as exc:
            logger.exception("Unexpected YouTube import failure yt_id=%s", parsed.video_id)
            _cleanup_partial_files(directory)
            raise InvalidInputError(_user_message_for_download_error(exc)) from exc
