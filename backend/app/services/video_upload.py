import logging
import shutil
import uuid
from pathlib import Path

from fastapi import Request, UploadFile

from app.core.config import Settings
from app.core.errors import (
    AppError,
    ClientDisconnectedError,
    InvalidInputError,
    PayloadTooLargeError,
)
from app.core.paths import job_dir, resolve_data_dir
from app.schemas.video import VideoUploadResponse
from app.services.ffprobe import enforce_probe_limits, run_ffprobe
from app.services.filenames import extension_from_filename, sanitize_original_filename
from app.services.import_lock import media_import_lock

logger = logging.getLogger(__name__)


def remove_job_tree(directory: Path) -> None:
    if directory.exists():
        shutil.rmtree(directory, ignore_errors=True)


async def stream_upload_file(
    upload: UploadFile,
    request: Request,
    destination: Path,
    *,
    max_bytes: int,
    chunk_size: int,
) -> int:
    """
    Stream multipart bytes to disk with a byte limit.

    Note: Starlette may spool large multipart parts to a temporary file before
    this handler runs; those bytes may already be on disk even if the client
    aborts later. We still enforce max_upload_bytes while reading UploadFile.
    """
    total = 0
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("wb") as handle:
        while True:
            if await request.is_disconnected():
                raise ClientDisconnectedError("Upload was cancelled.")

            chunk = await upload.read(chunk_size)
            if not chunk:
                break

            total += len(chunk)
            if total > max_bytes:
                raise PayloadTooLargeError(
                    "This file is too large. Choose a smaller video."
                )

            handle.write(chunk)

    if total == 0:
        raise InvalidInputError("This file is empty. Choose another video.")

    return total


def finalize_uploaded_video(
    *,
    video_id: uuid.UUID,
    stored_path: Path,
    original_filename: str,
    settings: Settings,
) -> VideoUploadResponse:
    probe = run_ffprobe(stored_path, settings)
    enforce_probe_limits(probe, settings)

    logger.info("Stored upload video_id=%s", video_id)

    return VideoUploadResponse(
        video_id=video_id,
        original_filename=original_filename,
        duration_seconds=probe.duration_seconds,
        width=probe.width,
        height=probe.height,
        has_audio=probe.has_audio,
        container=probe.container,
    )


async def accept_video_upload(
    upload: UploadFile,
    request: Request,
    settings: Settings,
) -> VideoUploadResponse:
    original_filename = sanitize_original_filename(upload.filename or "video.mp4")
    extension = extension_from_filename(original_filename)

    video_id = uuid.uuid4()
    directory = job_dir(settings.data_dir, video_id)
    partial_path = directory / "upload.part"
    stored_path = directory / f"source{extension}"

    resolve_data_dir(settings.data_dir).mkdir(parents=True, exist_ok=True)

    with media_import_lock():
        try:
            await stream_upload_file(
                upload,
                request,
                partial_path,
                max_bytes=settings.max_upload_bytes,
                chunk_size=settings.upload_chunk_size_bytes,
            )
            partial_path.replace(stored_path)
            return finalize_uploaded_video(
                video_id=video_id,
                stored_path=stored_path,
                original_filename=original_filename,
                settings=settings,
            )
        except AppError:
            remove_job_tree(directory)
            raise
        except Exception:
            logger.exception("Unexpected upload failure video_id=%s", video_id)
            remove_job_tree(directory)
            raise InvalidInputError(
                "We couldn't save this video. Please try again."
            ) from None
        finally:
            await upload.close()
            if partial_path.exists() and partial_path != stored_path:
                partial_path.unlink(missing_ok=True)
