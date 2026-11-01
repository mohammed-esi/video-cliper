"""On-disk portrait renders and deterministic cache keys."""

import hashlib
import json
import logging
import os
import re
import uuid
from pathlib import Path

from app.core.config import Settings
from app.core.errors import InvalidInputError, NotFoundError
from app.core.paths import assert_relative_to, job_dir, resolve_data_dir
from app.schemas.portrait import PortraitRenderRecord, PortraitsManifestFile
from app.schemas.tracking import (
    SCHEMA_VERSION,
    CropParams,
    DetectionCacheFile,
    CropPathFile,
    SourceFingerprint,
    TrackingParams,
)
from app.services.tracking.analysis_cache import (
    CROP_PATH_FILE,
    DETECTIONS_FILE,
    SCENES_FILE,
    TRACKING_FILE,
    fingerprint_source,
    read_artifact,
)
from app.services.tracking.face_detector import DEFAULT_MODEL_PATH
from app.services.tracking.source_analysis import build_detection_config
from app.services.ffprobe import run_ffprobe
from app.services.portrait_render import PORTRAIT_HEIGHT, PORTRAIT_WIDTH
from app.services.video_storage import find_source_video_path

logger = logging.getLogger(__name__)

PORTRAITS_SUBDIR = "portraits"
PORTRAITS_MANIFEST_NAME = "portraits.json"
ANALYSIS_SUBDIR = "analysis"
# Bump when FFmpeg portrait output semantics change (not tracking tuning).
PORTRAIT_RENDER_PIPELINE_VERSION = "2.5.2.1"
_RENDER_KEY_PATTERN = re.compile(r"^[a-f0-9]{32}$")


def analysis_directory(settings: Settings, video_id: uuid.UUID) -> Path:
    directory = job_dir(settings.data_dir, video_id) / ANALYSIS_SUBDIR
    directory.mkdir(parents=True, exist_ok=True)
    assert_relative_to(directory.resolve(), resolve_data_dir(settings.data_dir))
    return directory


def portraits_directory(settings: Settings, video_id: uuid.UUID) -> Path:
    directory = job_dir(settings.data_dir, video_id) / PORTRAITS_SUBDIR
    root = resolve_data_dir(settings.data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    assert_relative_to(directory.resolve(), root)
    return directory


def manifest_path(settings: Settings, video_id: uuid.UUID) -> Path:
    path = (job_dir(settings.data_dir, video_id) / PORTRAITS_MANIFEST_NAME).resolve()
    assert_relative_to(path, resolve_data_dir(settings.data_dir))
    return path


def _analysis_artifacts_digest(analysis_dir: Path) -> str | None:
    """Hash on-disk analysis artifacts so crop-path changes invalidate portrait cache."""
    digest = hashlib.sha256()
    found = False
    for name in (DETECTIONS_FILE, SCENES_FILE, TRACKING_FILE, CROP_PATH_FILE):
        path = analysis_dir / name
        if not path.is_file():
            continue
        found = True
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest() if found else None


def _tracking_config_digest(
    settings: Settings,
    source_path: Path,
    analysis_dir: Path,
) -> str:
    artifacts_digest = _analysis_artifacts_digest(analysis_dir)
    detection = read_artifact(analysis_dir / DETECTIONS_FILE, DetectionCacheFile)
    crop_path = read_artifact(analysis_dir / CROP_PATH_FILE, CropPathFile)
    if detection is not None and crop_path is not None:
        detection_config = detection.config
        tracking_params = crop_path.tracking_params
        crop_params = crop_path.crop_params
    else:
        probe = run_ffprobe(source_path, settings)
        fingerprint = fingerprint_source(source_path, probe)
        detection_config = build_detection_config(DEFAULT_MODEL_PATH, fingerprint)
        tracking_params = TrackingParams()
        crop_params = CropParams()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "pipeline": PORTRAIT_RENDER_PIPELINE_VERSION,
        "detection": detection_config.model_dump(mode="json"),
        "tracking_params": tracking_params.model_dump(mode="json"),
        "crop_params": crop_params.model_dump(mode="json"),
        "output": {"width": PORTRAIT_WIDTH, "height": PORTRAIT_HEIGHT},
        "analysis_artifacts_sha256": artifacts_digest,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_portrait_render_key(
    *,
    source: SourceFingerprint,
    clip_id: uuid.UUID,
    start_time: float,
    end_time: float,
    config_digest: str,
) -> str:
    payload = {
        "config_digest": config_digest,
        "source": source.model_dump(mode="json"),
        "clip_id": str(clip_id),
        "start_time": round(start_time, 3),
        "end_time": round(end_time, 3),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def portrait_file_name(render_key: str) -> str:
    if not _RENDER_KEY_PATTERN.fullmatch(render_key):
        raise InvalidInputError("Invalid portrait render key.")
    return f"{render_key}.mp4"


def portrait_file_path(settings: Settings, video_id: uuid.UUID, render_key: str) -> Path:
    path = (portraits_directory(settings, video_id) / portrait_file_name(render_key)).resolve()
    root = resolve_data_dir(settings.data_dir)
    if not path.is_relative_to(root):
        raise InvalidInputError("Invalid portrait path.")
    return path


def read_portraits_manifest(settings: Settings, video_id: uuid.UUID) -> PortraitsManifestFile:
    path = manifest_path(settings, video_id)
    if not path.is_file():
        return PortraitsManifestFile(video_id=video_id, renders=[])
    data = json.loads(path.read_text(encoding="utf-8"))
    return PortraitsManifestFile.model_validate(data)


def write_portraits_manifest(settings: Settings, manifest: PortraitsManifestFile) -> None:
    path = manifest_path(settings, manifest.video_id)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def find_portrait_record(
    settings: Settings, video_id: uuid.UUID, clip_id: uuid.UUID, render_key: str
) -> PortraitRenderRecord | None:
    manifest = read_portraits_manifest(settings, video_id)
    for record in manifest.renders:
        if record.clip_id != clip_id or record.render_key != render_key:
            continue
        file_path = portrait_file_path(settings, video_id, render_key)
        if file_path.is_file() and file_path.stat().st_size > 0:
            return record
    return None


def current_portrait_record(
    settings: Settings, video_id: uuid.UUID, clip_id: uuid.UUID
) -> PortraitRenderRecord | None:
    """Portrait that matches the clip's current trim and analysis configuration."""
    clip = get_clip_from_manifest(settings, video_id, clip_id)
    source_path = find_source_video_path(settings, video_id)
    render_key = build_render_key_for_clip(
        settings,
        video_id,
        clip_id,
        start_time=clip.start_time,
        end_time=clip.end_time,
        source_path=source_path,
    )
    record = find_portrait_record(settings, video_id, clip_id, render_key)
    if record is None:
        return None
    if (
        round(record.start_time, 3) != round(clip.start_time, 3)
        or round(record.end_time, 3) != round(clip.end_time, 3)
    ):
        return None
    return record


def commit_portrait_render(
    settings: Settings,
    video_id: uuid.UUID,
    record: PortraitRenderRecord,
) -> None:
    """Register a finished portrait and drop superseded files for the same clip."""
    manifest = read_portraits_manifest(settings, video_id)
    previous_names = {
        entry.storage_name
        for entry in manifest.renders
        if entry.clip_id == record.clip_id and entry.render_key != record.render_key
    }
    manifest = PortraitsManifestFile(
        video_id=video_id,
        renders=[entry for entry in manifest.renders if entry.clip_id != record.clip_id]
        + [record],
    )
    write_portraits_manifest(settings, manifest)
    portraits_dir = portraits_directory(settings, video_id)
    for name in previous_names:
        (portraits_dir / name).unlink(missing_ok=True)


def resolve_source_fingerprint(settings: Settings, source_path: Path) -> SourceFingerprint:
    probe = run_ffprobe(source_path, settings)
    return fingerprint_source(source_path, probe)


def build_render_key_for_clip(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
    *,
    start_time: float,
    end_time: float,
    source_path: Path,
) -> str:
    analysis_dir = analysis_directory(settings, video_id)
    digest = _tracking_config_digest(settings, source_path, analysis_dir)
    source = resolve_source_fingerprint(settings, source_path)
    return compute_portrait_render_key(
        source=source,
        clip_id=clip_id,
        start_time=start_time,
        end_time=end_time,
        config_digest=digest,
    )


def get_clip_from_manifest(settings: Settings, video_id: uuid.UUID, clip_id: uuid.UUID):
    from app.services.clip_storage import read_clips_manifest

    manifest = read_clips_manifest(settings, video_id)
    for clip in manifest.clips:
        if clip.clip_id == clip_id:
            return clip
    raise NotFoundError("Clip not found.")
