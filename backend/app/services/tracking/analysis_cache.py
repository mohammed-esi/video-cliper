"""On-disk cache for source-analysis artifacts: atomic writes, validated reads."""

import logging
import os
import uuid
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.paths import assert_relative_to, job_dir, resolve_data_dir
from app.schemas.tracking import SourceFingerprint
from app.services.ffprobe import ProbeResult

logger = logging.getLogger(__name__)

ANALYSIS_SUBDIR = "analysis"
DETECTIONS_FILE = "detections.json"
SCENES_FILE = "scenes.json"
TRACKING_FILE = "tracking.json"
CROP_PATH_FILE = "crop_path.json"

ModelT = TypeVar("ModelT", bound=BaseModel)


def analysis_directory(settings: Settings, video_id: uuid.UUID) -> Path:
    directory = job_dir(settings.data_dir, video_id) / ANALYSIS_SUBDIR
    directory.mkdir(parents=True, exist_ok=True)
    assert_relative_to(directory.resolve(), resolve_data_dir(settings.data_dir))
    return directory


def fingerprint_source(source_path: Path, probe: ProbeResult) -> SourceFingerprint:
    """Cheap identity: any re-upload or edit changes size or modification time."""
    stat = source_path.stat()
    return SourceFingerprint(
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        width=probe.width,
        height=probe.height,
        duration_seconds=probe.duration_seconds,
    )


def write_artifact(path: Path, model: BaseModel) -> None:
    """Write via a temp file and rename so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    try:
        temp_path.write_text(model.model_dump_json(), encoding="utf-8")
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise


def read_artifact(path: Path, model_type: type[ModelT]) -> ModelT | None:
    """Parse and schema-validate an artifact; any problem is a cache miss, not a crash."""
    if not path.is_file():
        return None
    try:
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, ValueError) as exc:
        logger.warning("Ignoring unreadable analysis cache file %s: %s", path.name, exc)
        return None
