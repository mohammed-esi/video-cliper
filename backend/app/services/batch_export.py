"""Batch ZIP export using cached or freshly rendered portrait MP4s."""

from __future__ import annotations

import logging
import os
import uuid
import zipfile
from pathlib import Path

from app.core.config import Settings
from app.core.errors import InvalidInputError, MediaProcessingError, NotFoundError
from app.core.paths import assert_relative_to, job_dir, resolve_data_dir
from app.schemas.batch_export import BatchExportRequest
from app.schemas.job import JobOperation, JobResponse, JobStatus
from app.services.clip_trim_revision import clip_trim_revision
from app.services.job_context import JobExecutionContext
from app.services.job_operations import ProgressCallback
from app.services.job_persistence import read_job
from app.services.portrait_clip_render import render_portrait_for_clip_sync
from app.services.portrait_storage import get_clip_from_manifest, portrait_file_path
from app.services.portrait_streaming import portrait_export_filename
from app.services import job_manager

logger = logging.getLogger(__name__)


def exports_directory(settings: Settings, video_id: uuid.UUID) -> Path:
    directory = (job_dir(settings.data_dir, video_id) / "exports").resolve()
    root = resolve_data_dir(settings.data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    assert_relative_to(directory, root)
    return directory


def batch_zip_path(settings: Settings, video_id: uuid.UUID, job_id: uuid.UUID) -> Path:
    path = (exports_directory(settings, video_id) / f"{job_id}.zip").resolve()
    assert_relative_to(path, resolve_data_dir(settings.data_dir))
    return path


def normalize_batch_selection(
    settings: Settings,
    video_id: uuid.UUID,
    request: BatchExportRequest,
) -> tuple[list[uuid.UUID], dict[str, str]]:
    if not request.clips:
        raise InvalidInputError("Select at least one clip to export.")

    ordered_ids: list[uuid.UUID] = []
    revisions: dict[str, str] = {}
    seen: set[uuid.UUID] = set()

    for item in request.clips:
        if item.clip_id in seen:
            continue
        seen.add(item.clip_id)
        clip = get_clip_from_manifest(settings, video_id, item.clip_id)
        expected = clip_trim_revision(clip.start_time, clip.end_time)
        if item.trim_revision != expected:
            raise InvalidInputError(
                "A selected clip was edited after you chose it. "
                "Return to the editor and try again."
            )
        ordered_ids.append(item.clip_id)
        revisions[str(item.clip_id)] = item.trim_revision

    if not ordered_ids:
        raise InvalidInputError("Select at least one clip to export.")

    return ordered_ids, revisions


def _assert_trim_unchanged(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
    expected_revision: str,
) -> None:
    clip = get_clip_from_manifest(settings, video_id, clip_id)
    current = clip_trim_revision(clip.start_time, clip.end_time)
    if current != expected_revision:
        raise MediaProcessingError(
            "A clip's trim changed during export. Please start a new export."
        )


def start_batch_export_job(
    settings: Settings,
    video_id: uuid.UUID,
    request: BatchExportRequest,
) -> JobResponse:
    clip_ids, revisions = normalize_batch_selection(settings, video_id, request)
    return job_manager.create_batch_export_job(
        video_id=video_id,
        clip_ids=clip_ids,
        trim_revisions=revisions,
    )


def run_batch_export_clips(
    update_progress: ProgressCallback,
    context: JobExecutionContext,
) -> dict[str, object]:
    settings = context.settings
    job = read_job(settings, context.job_id)
    if job is None:
        raise MediaProcessingError("Export job was lost. Please try again.")
    if job.batch_clip_ids is None or job.batch_trim_revisions is None:
        raise InvalidInputError("Batch export job is missing clip selection.")

    video_id = context.video_id
    clip_ids = job.batch_clip_ids
    revisions = job.batch_trim_revisions
    total = len(clip_ids)
    zip_path = batch_zip_path(settings, video_id, context.job_id)
    zip_tmp = zip_path.with_suffix(".zip.part")

    if zip_tmp.exists():
        zip_tmp.unlink()
    if zip_path.exists():
        zip_path.unlink()

    used_names: set[str] = set()
    portrait_paths: list[tuple[str, Path]] = []

    try:
        for index, clip_id in enumerate(clip_ids):
            revision = revisions.get(str(clip_id))
            if revision is None:
                raise MediaProcessingError("Export selection is invalid. Please try again.")

            _assert_trim_unchanged(settings, video_id, clip_id, revision)

            def clip_progress(fraction: float) -> None:
                overall = (index + max(0.0, min(1.0, fraction))) / total
                update_progress(overall)
                job_manager.update_batch_export_progress(
                    context.job_id,
                    phase="rendering",
                    current_index=index + 1,
                    total=total,
                    clip_id=clip_id,
                )

            clip_progress(0.0)
            record = render_portrait_for_clip_sync(
                settings,
                video_id,
                clip_id,
                on_progress=clip_progress,
            )
            if record is None:
                raise MediaProcessingError(
                    "A clip's trim changed during export. Please start a new export."
                )
            _assert_trim_unchanged(settings, video_id, clip_id, revision)

            path = portrait_file_path(settings, video_id, record.render_key)
            if not path.is_file():
                raise MediaProcessingError(
                    "Portrait file is missing after rendering. Please try again."
                )

            entry_name = _unique_zip_entry_name(
                portrait_export_filename(record),
                used_names,
            )
            used_names.add(entry_name)
            portrait_paths.append((entry_name, path))
            clip_progress(1.0)

        update_progress(max(0.95, (total - 0.05) / total))
        job_manager.update_batch_export_progress(
            context.job_id,
            phase="packaging",
            current_index=total,
            total=total,
            clip_id=None,
        )

        with zipfile.ZipFile(
            zip_tmp,
            mode="w",
            compression=zipfile.ZIP_STORED,
            allowZip64=True,
        ) as archive:
            for entry_name, path in portrait_paths:
                archive.write(path, arcname=entry_name)

        os.replace(zip_tmp, zip_path)
        update_progress(1.0)

        return {
            "operation": JobOperation.BATCH_EXPORT_CLIPS.value,
            "clip_count": total,
            "zip_storage_name": zip_path.name,
            "trim_revisions": dict(revisions),
            "clip_ids": [str(clip_id) for clip_id in clip_ids],
            "phase": "completed",
        }
    except Exception:
        zip_tmp.unlink(missing_ok=True)
        zip_path.unlink(missing_ok=True)
        raise


def _unique_zip_entry_name(base: str, used: set[str]) -> str:
    if base not in used:
        return base
    stem, dot, ext = base.partition(".")
    suffix = ext if dot else "mp4"
    name_stem = stem if dot else base
    counter = 2
    while True:
        candidate = f"{name_stem}-{counter}.{suffix}"
        if candidate not in used:
            return candidate
        counter += 1


def validate_batch_export_download(
    settings: Settings,
    video_id: uuid.UUID,
    job_id: uuid.UUID,
) -> Path:
    job = read_job(settings, job_id)
    if job is None:
        raise NotFoundError("Export not found.")
    if job.video_id != video_id:
        raise NotFoundError("Export not found.")
    if job.operation != JobOperation.BATCH_EXPORT_CLIPS:
        raise NotFoundError("Export not found.")
    if job.status != JobStatus.COMPLETED:
        raise NotFoundError("This export is not ready yet.")
    if job.batch_clip_ids is None or job.batch_trim_revisions is None:
        raise NotFoundError("Export not found.")

    for clip_id in job.batch_clip_ids:
        revision = job.batch_trim_revisions.get(str(clip_id))
        if revision is None:
            raise NotFoundError("Export is outdated. Please export again.")
        try:
            _assert_trim_unchanged(settings, video_id, clip_id, revision)
        except MediaProcessingError as exc:
            raise NotFoundError(exc.message) from exc
        record_path = _current_portrait_path(settings, video_id, clip_id)
        if record_path is None:
            raise NotFoundError("Export is outdated. Please export again.")

    zip_path = batch_zip_path(settings, video_id, job_id)
    if not zip_path.is_file():
        raise NotFoundError("Export file is missing. Please export again.")

    return zip_path


def batch_export_download_filename(job_id: uuid.UUID) -> str:
    short = str(job_id).split("-", maxsplit=1)[0]
    return f"clips-export-{short}.zip"


def _current_portrait_path(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
) -> Path | None:
    from app.services.portrait_storage import current_portrait_record

    record = current_portrait_record(settings, video_id, clip_id)
    if record is None:
        return None
    path = portrait_file_path(settings, video_id, record.render_key)
    return path if path.is_file() else None
