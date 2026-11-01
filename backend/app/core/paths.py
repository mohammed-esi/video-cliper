import uuid
from pathlib import Path

from app.core.errors import InvalidInputError


def resolve_data_dir(data_dir: Path) -> Path:
    return data_dir.expanduser().resolve()


def job_dir(data_dir: Path, video_id: uuid.UUID) -> Path:
    root = resolve_data_dir(data_dir)
    directory = (root / "jobs" / str(video_id)).resolve()
    if not directory.is_relative_to(root):
        raise InvalidInputError("Invalid storage path.")
    return directory


def processing_jobs_dir(data_dir: Path) -> Path:
    root = resolve_data_dir(data_dir)
    directory = (root / "processing_jobs").resolve()
    if not directory.is_relative_to(root):
        raise InvalidInputError("Invalid storage path.")
    return directory


def processing_job_file(data_dir: Path, job_id: uuid.UUID) -> Path:
    directory = processing_jobs_dir(data_dir)
    path = (directory / f"{job_id}.json").resolve()
    assert_relative_to(path, resolve_data_dir(data_dir))
    return path


def assert_relative_to(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    base = root.resolve()
    if not resolved.is_relative_to(base):
        raise InvalidInputError("Invalid storage path.")
    return resolved
