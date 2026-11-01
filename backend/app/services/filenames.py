import re
from pathlib import Path

from app.core.errors import InvalidInputError

ALLOWED_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".webm", ".m4v"})

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_DISPLAY_FILENAME_LEN = 200


def sanitize_original_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = _CONTROL_CHARS.sub("", name)
    if not name or name in {".", ".."}:
        raise InvalidInputError("The file needs a valid name.")
    if len(name) > _MAX_DISPLAY_FILENAME_LEN:
        stem = Path(name).stem
        suffix = Path(name).suffix
        keep = _MAX_DISPLAY_FILENAME_LEN - len(suffix)
        name = f"{stem[: max(keep, 1)]}{suffix}"
    return name


def extension_from_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise InvalidInputError(
            "This file type is not supported. Use MP4, MOV, MKV, WebM or M4V."
        )
    return suffix
