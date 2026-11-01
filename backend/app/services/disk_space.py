import shutil
from pathlib import Path

from app.core.config import Settings
from app.core.errors import MediaProcessingError


def ensure_disk_space_for_bytes(settings: Settings, path: Path, required_bytes: int) -> None:
    target = path.expanduser().resolve()
    usage = shutil.disk_usage(target)
    available = usage.free
    margin = settings.disk_space_safety_margin_bytes
    if available < required_bytes + margin:
        raise MediaProcessingError(
            "Not enough disk space to generate clips. Free up space and try again."
        )
