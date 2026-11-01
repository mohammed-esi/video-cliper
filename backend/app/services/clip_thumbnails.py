import json
import logging
import os
import time
import uuid
from pathlib import Path

from starlette.responses import FileResponse

from app.core.config import Settings
from app.core.errors import MediaProcessingError, NotFoundError
from app.core.paths import assert_relative_to, job_dir, resolve_data_dir
from app.schemas.clip import ClipMetadata
from app.services.clip_storage import find_clip_file, read_clips_manifest
from app.services.ffmpeg_runner import ffmpeg_input_argument, run_ffmpeg
from app.services.video_storage import find_source_video_path

logger = logging.getLogger(__name__)

THUMBNAILS_SUBDIR = "thumbnails"
THUMBNAIL_MAX_WIDTH = 320
THUMBNAIL_JPEG_QUALITY = 4
FFMPEG_BUSY_RETRY_SECONDS = 30.0
FFMPEG_BUSY_POLL_SECONDS = 0.2
FFMPEG_BUSY_MESSAGE = "Another FFmpeg process is already running."


def thumbnail_midpoint(start_time: float, end_time: float) -> float:
    return (start_time + end_time) / 2.0


def thumbnails_directory(settings: Settings, video_id: uuid.UUID) -> Path:
    directory = job_dir(settings.data_dir, video_id) / THUMBNAILS_SUBDIR
    root = resolve_data_dir(settings.data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    assert_relative_to(directory.resolve(), root)
    return directory


def _thumbnail_image_path(settings: Settings, video_id: uuid.UUID, clip_id: uuid.UUID) -> Path:
    path = (thumbnails_directory(settings, video_id) / f"{clip_id}.jpg").resolve()
    assert_relative_to(path, resolve_data_dir(settings.data_dir))
    return path


def _thumbnail_meta_path(settings: Settings, video_id: uuid.UUID, clip_id: uuid.UUID) -> Path:
    path = (thumbnails_directory(settings, video_id) / f"{clip_id}.json").resolve()
    assert_relative_to(path, resolve_data_dir(settings.data_dir))
    return path


def _read_cache_meta(meta_path: Path) -> dict[str, float] | None:
    if not meta_path.is_file():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return {
            "start_time": float(data["start_time"]),
            "end_time": float(data["end_time"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _cache_matches_clip(meta: dict[str, float] | None, clip: ClipMetadata) -> bool:
    if meta is None:
        return False
    return (
        abs(meta["start_time"] - clip.start_time) < 1e-3
        and abs(meta["end_time"] - clip.end_time) < 1e-3
    )


def invalidate_clip_thumbnail(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
) -> None:
    _thumbnail_image_path(settings, video_id, clip_id).unlink(missing_ok=True)
    _thumbnail_meta_path(settings, video_id, clip_id).unlink(missing_ok=True)


def _write_cache_meta(meta_path: Path, clip: ClipMetadata, timestamp: float) -> None:
    payload = {
        "start_time": clip.start_time,
        "end_time": clip.end_time,
        "timestamp": timestamp,
    }
    tmp_path = meta_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp_path, meta_path)


def _generate_thumbnail_file(
    settings: Settings,
    *,
    source_path: Path,
    output_path: Path,
    timestamp: float,
) -> None:
    scale = f"scale={THUMBNAIL_MAX_WIDTH}:-2"
    command = [
        settings.ffmpeg_path,
        "-nostdin",
        "-y",
        "-ss",
        f"{timestamp:.6f}",
        "-i",
        ffmpeg_input_argument(source_path),
        "-frames:v",
        "1",
        "-vf",
        scale,
        "-q:v",
        str(THUMBNAIL_JPEG_QUALITY),
        "-f",
        "image2",
        "-update",
        "1",
        str(output_path),
    ]
    deadline = time.monotonic() + FFMPEG_BUSY_RETRY_SECONDS
    last_busy: MediaProcessingError | None = None
    while time.monotonic() < deadline:
        try:
            run_ffmpeg(command, timeout_seconds=30.0, cancelled=None)
            break
        except MediaProcessingError as exc:
            if exc.message != FFMPEG_BUSY_MESSAGE:
                logger.warning(
                    "Clip thumbnail ffmpeg failed for %s: %s",
                    output_path.name,
                    exc.message,
                )
                raise MediaProcessingError(
                    "We couldn't generate this clip thumbnail."
                ) from exc
            last_busy = exc
            time.sleep(FFMPEG_BUSY_POLL_SECONDS)
    else:
        raise last_busy or MediaProcessingError(
            "We couldn't generate this clip thumbnail."
        )

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise MediaProcessingError("We couldn't generate this clip thumbnail.")


def _find_clip_metadata(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
) -> ClipMetadata:
    manifest = read_clips_manifest(settings, video_id)
    for clip in manifest.clips:
        if clip.clip_id == clip_id:
            find_clip_file(settings, video_id, clip_id)
            return clip
    raise NotFoundError("Clip not found.")


def get_or_create_clip_thumbnail_path(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
) -> Path:
    clip = _find_clip_metadata(settings, video_id, clip_id)
    image_path = _thumbnail_image_path(settings, video_id, clip_id)
    meta_path = _thumbnail_meta_path(settings, video_id, clip_id)
    cached = _read_cache_meta(meta_path)

    if image_path.is_file() and _cache_matches_clip(cached, clip):
        return image_path

    source_path = find_source_video_path(settings, video_id)
    timestamp = thumbnail_midpoint(clip.start_time, clip.end_time)
    # FFmpeg needs a standard image extension (e.g. .jpg), not ".jpg.tmp".
    tmp_image = image_path.with_suffix(".tmp.jpg")
    try:
        _generate_thumbnail_file(
            settings,
            source_path=source_path,
            output_path=tmp_image,
            timestamp=timestamp,
        )
        os.replace(tmp_image, image_path)
        _write_cache_meta(meta_path, clip, timestamp)
    except Exception:
        tmp_image.unlink(missing_ok=True)
        raise

    return image_path


def build_clip_thumbnail_response(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
) -> FileResponse:
    try:
        path = get_or_create_clip_thumbnail_path(settings, video_id, clip_id)
    except NotFoundError:
        raise
    except MediaProcessingError:
        raise
    except Exception as exc:
        logger.exception(
            "Clip thumbnail failed video_id=%s clip_id=%s",
            video_id,
            clip_id,
        )
        raise MediaProcessingError(
            "We couldn't generate this clip thumbnail."
        ) from exc

    return FileResponse(
        path=path,
        media_type="image/jpeg",
        filename=f"clip-{clip_id}-thumb.jpg",
        headers={"Cache-Control": "private, max-age=86400"},
    )
