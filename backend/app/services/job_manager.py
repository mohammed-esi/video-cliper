import logging
import threading
import uuid
from typing import Any

from app.core.config import Settings
from app.core.errors import (
    InvalidInputError,
    JobConflictError,
    JobQueueFullError,
    MediaProcessingError,
    NotFoundError,
)
from app.schemas.portrait import PortraitRenderRecord
from app.services.job_context import JobExecutionContext
from app.schemas.job import CreateJobRequest, JobOperation, JobResponse, JobStatus
from app.services.job_operations import get_operation_handler
from app.services.job_persistence import StoredJob, list_jobs, read_job, utc_now, write_job
from app.services.video_storage import find_source_video_path

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_settings: Settings | None = None
_jobs: dict[uuid.UUID, StoredJob] = {}
_active_video_ids: set[uuid.UUID] = set()


def initialize(settings: Settings) -> None:
    global _settings, _jobs, _active_video_ids
    with _lock:
        _settings = settings
        _jobs = {job.job_id: job for job in list_jobs(settings)}
        _active_video_ids = {
            job.video_id
            for job in _jobs.values()
            if job.status in {JobStatus.QUEUED, JobStatus.PROCESSING}
        }
        _recover_interrupted_jobs()


def _require_settings() -> Settings:
    if _settings is None:
        raise RuntimeError("Job manager is not initialized.")
    return _settings


def _to_response(job: StoredJob) -> JobResponse:
    return JobResponse(
        job_id=job.job_id,
        video_id=job.video_id,
        operation=job.operation,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
        updated_at=job.updated_at,
        error_message=job.error_message,
        result=job.result,
    )


def _persist(job: StoredJob) -> None:
    settings = _require_settings()
    write_job(settings, job)
    _jobs[job.job_id] = job


def _recover_interrupted_jobs() -> None:
    settings = _require_settings()
    for job in list(_jobs.values()):
        if job.status not in {JobStatus.QUEUED, JobStatus.PROCESSING}:
            continue
        recovered = job.model_copy(
            update={
                "status": JobStatus.FAILED,
                "progress": 0.0,
                "error_message": "Processing was interrupted by a server restart.",
                "updated_at": utc_now(),
            }
        )
        write_job(settings, recovered)
        _jobs[job.job_id] = recovered
        _active_video_ids.discard(job.video_id)
        logger.info("Marked interrupted job job_id=%s as failed", job.job_id)


def create_job(request: CreateJobRequest) -> JobResponse:
    settings = _require_settings()
    find_source_video_path(settings, request.video_id)
    if request.operation == JobOperation.RENDER_PORTRAIT_CLIP:
        if request.clip_id is None or not request.render_key:
            raise InvalidInputError("Portrait render jobs require a clip id and render key.")
        from app.services.portrait_storage import get_clip_from_manifest

        get_clip_from_manifest(settings, request.video_id, request.clip_id)

    with _lock:
        if request.video_id in _active_video_ids:
            raise JobConflictError()

        queued_count = sum(
            1 for job in _jobs.values() if job.status == JobStatus.QUEUED
        )
        if queued_count >= settings.max_processing_queue_size:
            raise JobQueueFullError()

        now = utc_now()
        job = StoredJob(
            job_id=uuid.uuid4(),
            video_id=request.video_id,
            operation=request.operation,
            status=JobStatus.QUEUED,
            progress=0.0,
            created_at=now,
            updated_at=now,
            clip_id=request.clip_id,
            render_key=request.render_key,
        )
        _persist(job)
        _active_video_ids.add(request.video_id)
        logger.info(
            "Queued job job_id=%s video_id=%s operation=%s",
            job.job_id,
            job.video_id,
            job.operation.value,
        )
        return _to_response(job)


def create_batch_export_job(
    *,
    video_id: uuid.UUID,
    clip_ids: list[uuid.UUID],
    trim_revisions: dict[str, str],
) -> JobResponse:
    settings = _require_settings()
    find_source_video_path(settings, video_id)
    if not clip_ids:
        raise InvalidInputError("Select at least one clip to export.")

    with _lock:
        if video_id in _active_video_ids:
            raise JobConflictError()

        queued_count = sum(
            1 for job in _jobs.values() if job.status == JobStatus.QUEUED
        )
        if queued_count >= settings.max_processing_queue_size:
            raise JobQueueFullError()

        now = utc_now()
        job = StoredJob(
            job_id=uuid.uuid4(),
            video_id=video_id,
            operation=JobOperation.BATCH_EXPORT_CLIPS,
            status=JobStatus.QUEUED,
            progress=0.0,
            created_at=now,
            updated_at=now,
            batch_clip_ids=list(clip_ids),
            batch_trim_revisions=dict(trim_revisions),
            result={
                "operation": JobOperation.BATCH_EXPORT_CLIPS.value,
                "phase": "queued",
                "current_index": 0,
                "total": len(clip_ids),
            },
        )
        _persist(job)
        _active_video_ids.add(video_id)
        logger.info(
            "Queued batch export job_id=%s video_id=%s clips=%s",
            job.job_id,
            video_id,
            len(clip_ids),
        )
        return _to_response(job)


def update_batch_export_progress(
    job_id: uuid.UUID,
    *,
    phase: str,
    current_index: int,
    total: int,
    clip_id: uuid.UUID | None,
) -> None:
    payload: dict[str, Any] = {
        "operation": JobOperation.BATCH_EXPORT_CLIPS.value,
        "phase": phase,
        "current_index": current_index,
        "total": total,
    }
    if clip_id is not None:
        payload["clip_id"] = str(clip_id)
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        if job.status not in {JobStatus.QUEUED, JobStatus.PROCESSING}:
            return
        updated = job.model_copy(
            update={"result": payload, "updated_at": utc_now()}
        )
        _persist(updated)
        _jobs[job_id] = updated


def create_completed_portrait_job(
    *,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
    render_key: str,
    record: PortraitRenderRecord,
) -> JobResponse:
    """Return a synthetic completed job when a portrait file is already cached."""
    settings = _require_settings()
    now = utc_now()
    job = StoredJob(
        job_id=uuid.uuid4(),
        video_id=video_id,
        operation=JobOperation.RENDER_PORTRAIT_CLIP,
        status=JobStatus.COMPLETED,
        progress=1.0,
        created_at=now,
        updated_at=now,
        clip_id=clip_id,
        render_key=render_key,
        result={
            "operation": JobOperation.RENDER_PORTRAIT_CLIP.value,
            "cached": True,
            "stale_discarded": False,
            "clip_id": str(record.clip_id),
            "render_key": record.render_key,
            "start_time": record.start_time,
            "end_time": record.end_time,
            "storage_name": record.storage_name,
            "width": record.width,
            "height": record.height,
            "has_audio": record.has_audio,
        },
    )
    _persist(job)
    return _to_response(job)


def get_job(job_id: uuid.UUID) -> JobResponse:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            job = read_job(_require_settings(), job_id)
            if job is None:
                raise NotFoundError("Job not found.")
            _jobs[job_id] = job
        return _to_response(job)


def _update_job(job_id: uuid.UUID, **updates: Any) -> StoredJob:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            raise NotFoundError("Job not found.")
        if job.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
            meaningful = updates.keys() - {"updated_at"}
            new_status = updates.get("status")
            if meaningful and not (
                meaningful == {"status"} and new_status == job.status
            ):
                logger.info(
                    "Ignoring update to terminal job job_id=%s (status=%s)",
                    job_id,
                    job.status.value,
                )
                return job
        updated = job.model_copy(update={**updates, "updated_at": utc_now()})
        _persist(updated)
        if updated.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
            _active_video_ids.discard(updated.video_id)
        return updated


def run_job(job_id: uuid.UUID) -> None:
    settings = _require_settings()
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            logger.warning("run_job called for unknown job_id=%s", job_id)
            return
        if job.status != JobStatus.QUEUED:
            logger.warning("run_job skipped job_id=%s status=%s", job_id, job.status)
            return
        operation = job.operation
        video_id = job.video_id
        clip_id = job.clip_id
        render_key = job.render_key

    try:
        find_source_video_path(settings, video_id)
    except NotFoundError as exc:
        _update_job(
            job_id,
            status=JobStatus.FAILED,
            progress=0.0,
            error_message=exc.message,
        )
        return

    _update_job(job_id, status=JobStatus.PROCESSING, progress=0.0, error_message=None)

    def update_progress(value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))
        _update_job(job_id, progress=clamped)

    context = JobExecutionContext(
        job_id=job_id,
        video_id=video_id,
        settings=settings,
        clip_id=clip_id,
        render_key=render_key,
    )

    try:
        handler = get_operation_handler(operation)
        result = handler(update_progress, context)
        _update_job(
            job_id,
            status=JobStatus.COMPLETED,
            progress=1.0,
            result=result,
            error_message=None,
        )
        logger.info("Completed job job_id=%s", job_id)
    except MediaProcessingError as exc:
        logger.info("Processing failed job_id=%s reason=%s", job_id, exc.message)
        _update_job(
            job_id,
            status=JobStatus.FAILED,
            progress=0.0,
            error_message=exc.message,
        )
    except Exception:
        logger.exception("Processing failed job_id=%s", job_id)
        _update_job(
            job_id,
            status=JobStatus.FAILED,
            progress=0.0,
            error_message="Video processing failed. Please try again.",
        )


def reset_for_tests() -> None:
    global _settings, _jobs, _active_video_ids
    with _lock:
        _settings = None
        _jobs = {}
        _active_video_ids = set()
