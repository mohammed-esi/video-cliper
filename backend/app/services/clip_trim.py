import uuid
from app.core.config import Settings
from app.core.errors import InvalidInputError, NotFoundError
from app.schemas.clip import ClipListResponse, ClipMetadata, ClipTrimUpdate
from app.services.clip_storage import read_clips_manifest, write_clips_manifest
from app.services.clip_thumbnails import invalidate_clip_thumbnail
from app.services.ffprobe import run_ffprobe
from app.services.video_storage import find_source_video_path

MIN_TRIM_DURATION_SECONDS = 0.1
TIME_QUANTUM = 0.1


def _round_to_tenth(value: float) -> float:
    return round(value * 10) / 10


def validate_trim_range(
    *,
    start_time: float,
    end_time: float,
    source_duration: float,
    min_duration: float = MIN_TRIM_DURATION_SECONDS,
) -> tuple[float, float]:
    if end_time - start_time + 1e-6 < min_duration:
        raise InvalidInputError(
            f"Clips must be at least {min_duration:.1f} seconds long."
        )

    start = _round_to_tenth(start_time)
    end = _round_to_tenth(end_time)

    if start < 0:
        raise InvalidInputError("Start time cannot be before the beginning of the video.")
    if end > source_duration + 1e-6:
        raise InvalidInputError("End time cannot be past the end of the source video.")
    if end <= start:
        raise InvalidInputError("End time must be after the start time.")
    return start, end


def list_clips_with_source_duration(
    settings: Settings,
    video_id: uuid.UUID,
) -> ClipListResponse:
    manifest = read_clips_manifest(settings, video_id)
    source_path = find_source_video_path(settings, video_id)
    source_probe = run_ffprobe(source_path, settings)
    return ClipListResponse(
        video_id=video_id,
        source_duration_seconds=source_probe.duration_seconds,
        clips=manifest.clips,
    )


def update_clip_trim(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
    update: ClipTrimUpdate,
) -> ClipMetadata:
    manifest = read_clips_manifest(settings, video_id)
    source_path = find_source_video_path(settings, video_id)
    source_probe = run_ffprobe(source_path, settings)

    start, end = validate_trim_range(
        start_time=update.start_time,
        end_time=update.end_time,
        source_duration=source_probe.duration_seconds,
    )

    updated_clip: ClipMetadata | None = None
    next_clips: list[ClipMetadata] = []
    for clip in manifest.clips:
        if clip.clip_id != clip_id:
            next_clips.append(clip)
            continue
        updated_clip = clip.model_copy(
            update={
                "start_time": start,
                "end_time": end,
                "duration": end - start,
            }
        )
        next_clips.append(updated_clip)

    if updated_clip is None:
        raise NotFoundError("Clip not found.")

    write_clips_manifest(settings, video_id, next_clips)
    invalidate_clip_thumbnail(settings, video_id, clip_id)
    return updated_clip
