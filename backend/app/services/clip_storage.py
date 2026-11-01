import json
import logging
import os
import uuid
from pathlib import Path

from app.core.config import Settings
from app.core.errors import InvalidInputError, NotFoundError
from app.core.paths import assert_relative_to, job_dir, resolve_data_dir
from app.schemas.clip import ClipMetadata, ClipsManifestFile

logger = logging.getLogger(__name__)

CLIPS_MANIFEST_NAME = "clips.json"
CLIPS_SUBDIR = "clips"


def clips_directory(settings: Settings, video_id: uuid.UUID) -> Path:
    directory = job_dir(settings.data_dir, video_id) / CLIPS_SUBDIR
    root = resolve_data_dir(settings.data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    assert_relative_to(directory.resolve(), root)
    return directory


def manifest_path(settings: Settings, video_id: uuid.UUID) -> Path:
    path = (job_dir(settings.data_dir, video_id) / CLIPS_MANIFEST_NAME).resolve()
    assert_relative_to(path, resolve_data_dir(settings.data_dir))
    return path


def write_clips_manifest(settings: Settings, video_id: uuid.UUID, clips: list[ClipMetadata]) -> None:
    payload = ClipsManifestFile(video_id=video_id, clips=clips).model_dump(mode="json")
    path = manifest_path(settings, video_id)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def read_clips_manifest(settings: Settings, video_id: uuid.UUID) -> ClipsManifestFile:
    path = manifest_path(settings, video_id)
    if not path.is_file():
        raise NotFoundError("No clips found for this video.")
    data = json.loads(path.read_text(encoding="utf-8"))
    response = ClipsManifestFile.model_validate(data)
    for clip in response.clips:
        find_clip_file(settings, video_id, clip.clip_id)
    return response


def find_clip_file(settings: Settings, video_id: uuid.UUID, clip_id: uuid.UUID) -> Path:
    root = resolve_data_dir(settings.data_dir)
    clip_path = (clips_directory(settings, video_id) / f"{clip_id}.mp4").resolve()
    if not clip_path.is_file():
        raise NotFoundError("Clip not found.")
    if not clip_path.is_relative_to(root):
        raise InvalidInputError("Invalid clip path.")
    return clip_path


def remove_clip_files(paths: list[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def remove_clips_except(settings: Settings, video_id: uuid.UUID, keep: set[Path]) -> None:
    resolved_keep = {path.resolve() for path in keep}
    for path in clips_directory(settings, video_id).glob("*.mp4"):
        if path.resolve() not in resolved_keep:
            path.unlink(missing_ok=True)


def commit_clips_manifest(
    settings: Settings,
    video_id: uuid.UUID,
    clips: list[ClipMetadata],
    keep: set[Path],
) -> None:
    """Atomically replace the manifest, then delete superseded clip files."""
    write_clips_manifest(settings, video_id, clips)
    try:
        remove_clips_except(settings, video_id, keep)
    except OSError as exc:
        logger.error(
            "Failed to remove superseded clip files video_id=%s: %s",
            video_id,
            exc,
            exc_info=True,
        )


def remove_generated_clips(settings: Settings, video_id: uuid.UUID) -> None:
    clips_dir = clips_directory(settings, video_id)
    for path in clips_dir.glob("*.mp4"):
        path.unlink(missing_ok=True)
    manifest = manifest_path(settings, video_id)
    manifest.unlink(missing_ok=True)
