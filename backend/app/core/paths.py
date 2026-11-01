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


def assert_relative_to(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    base = root.resolve()
    if not resolved.is_relative_to(base):
        raise InvalidInputError("Invalid storage path.")
    return resolved
