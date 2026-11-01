import uuid
from pathlib import Path

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.core.paths import assert_relative_to, job_dir, resolve_data_dir


def find_source_video_path(settings: Settings, video_id: uuid.UUID) -> Path:
    directory = job_dir(settings.data_dir, video_id)
    root = resolve_data_dir(settings.data_dir)
    if not directory.is_dir():
        raise NotFoundError("Video not found.")

    candidates = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.name.startswith("source.")
    )
    if not candidates:
        raise NotFoundError("Video not found.")

    source = assert_relative_to(candidates[0].resolve(), root)
    return source
