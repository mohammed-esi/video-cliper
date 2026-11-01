"""Portrait render jobs: cache keys, stale protection, and job integration."""

import logging
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.errors import InvalidInputError, JobConflictError, MediaProcessingError, NotFoundError
from app.schemas.job import CreateJobRequest, JobOperation, JobResponse
from app.schemas.portrait import PortraitRenderRecord
from app.services import job_manager
from app.services.clip_storage import read_clips_manifest
from app.services.ffprobe import run_ffprobe
from app.services.job_context import JobExecutionContext
from app.services.job_operations import ProgressCallback
from app.services.portrait_render import (
    PORTRAIT_HEIGHT,
    PORTRAIT_WIDTH,
    render_portrait_clip,
)
from app.services.portrait_storage import (
    analysis_directory,
    build_render_key_for_clip,
    commit_portrait_render,
    find_portrait_record,
    get_clip_from_manifest,
    portrait_file_path,
)
from app.services.video_storage import find_source_video_path

logger = logging.getLogger(__name__)

_inflight_lock = threading.Lock()
# (video_id, clip_id, render_key) -> job_id for in-process deduplication
_inflight_jobs: dict[tuple[str, str, str], uuid.UUID] = {}


@dataclass(frozen=True, slots=True)
class PortraitRenderPlan:
    video_id: uuid.UUID
    clip_id: uuid.UUID
    start_time: float
    end_time: float
    render_key: str
    output_path: Path
    cached_record: PortraitRenderRecord | None


def _inflight_key(video_id: uuid.UUID, clip_id: uuid.UUID, render_key: str) -> tuple[str, str, str]:
    return (str(video_id), str(clip_id), render_key)


def clear_portrait_inflight_for_tests() -> None:
    with _inflight_lock:
        _inflight_jobs.clear()


def load_clip_trim(settings: Settings, video_id: uuid.UUID, clip_id: uuid.UUID) -> tuple[float, float]:
    clip = get_clip_from_manifest(settings, video_id, clip_id)
    return clip.start_time, clip.end_time


def build_portrait_render_plan(
    settings: Settings, video_id: uuid.UUID, clip_id: uuid.UUID
) -> PortraitRenderPlan:
    source_path = find_source_video_path(settings, video_id)
    start_time, end_time = load_clip_trim(settings, video_id, clip_id)
    render_key = build_render_key_for_clip(
        settings,
        video_id,
        clip_id,
        start_time=start_time,
        end_time=end_time,
        source_path=source_path,
    )
    output_path = portrait_file_path(settings, video_id, render_key)
    cached = find_portrait_record(settings, video_id, clip_id, render_key)
    return PortraitRenderPlan(
        video_id=video_id,
        clip_id=clip_id,
        start_time=start_time,
        end_time=end_time,
        render_key=render_key,
        output_path=output_path,
        cached_record=cached,
    )


def get_inflight_portrait_job(
    settings: Settings, video_id: uuid.UUID, clip_id: uuid.UUID
) -> JobResponse | None:
    plan = build_portrait_render_plan(settings, video_id, clip_id)
    key = _inflight_key(video_id, clip_id, plan.render_key)
    with _inflight_lock:
        job_id = _inflight_jobs.get(key)
    if job_id is None:
        return None
    return job_manager.get_job(job_id)


def request_portrait_render(
    settings: Settings, video_id: uuid.UUID, clip_id: uuid.UUID
) -> JobResponse:
    """API entry: enqueue portrait render, reusing cache or an in-flight job."""
    get_clip_from_manifest(settings, video_id, clip_id)
    try:
        return enqueue_portrait_render(settings, video_id, clip_id)
    except JobConflictError:
        inflight = get_inflight_portrait_job(settings, video_id, clip_id)
        if inflight is not None:
            return inflight
        raise


def enqueue_portrait_render(
    settings: Settings, video_id: uuid.UUID, clip_id: uuid.UUID
) -> JobResponse:
    """Queue a portrait render job, reuse cache, or return an in-flight job for the same key."""
    plan = build_portrait_render_plan(settings, video_id, clip_id)
    if plan.cached_record is not None:
        return job_manager.create_completed_portrait_job(
            video_id=video_id,
            clip_id=clip_id,
            render_key=plan.render_key,
            record=plan.cached_record,
        )

    key = _inflight_key(video_id, clip_id, plan.render_key)
    request = CreateJobRequest(
        video_id=video_id,
        operation=JobOperation.RENDER_PORTRAIT_CLIP,
        clip_id=clip_id,
        render_key=plan.render_key,
    )
    with _inflight_lock:
        existing_job_id = _inflight_jobs.get(key)
        if existing_job_id is not None:
            return job_manager.get_job(existing_job_id)
        response = job_manager.create_job(request)
        _inflight_jobs[key] = response.job_id
        return response


def _release_inflight(video_id: uuid.UUID, clip_id: uuid.UUID, render_key: str) -> None:
    key = _inflight_key(video_id, clip_id, render_key)
    with _inflight_lock:
        _inflight_jobs.pop(key, None)


def _finalize_portrait_output(
    settings: Settings,
    *,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
    expected_start_time: float,
    expected_end_time: float,
    temp_output: Path,
) -> tuple[PortraitRenderRecord | None, bool]:
    """Move `temp_output` into place only if the clip trim still matches the queued range."""
    start_time, end_time = load_clip_trim(settings, video_id, clip_id)
    if round(start_time, 3) != round(expected_start_time, 3) or round(
        end_time, 3
    ) != round(expected_end_time, 3):
        temp_output.unlink(missing_ok=True)
        logger.info(
            "Discarded stale portrait render video_id=%s clip_id=%s expected_trim=%s-%s current_trim=%s-%s",
            video_id,
            clip_id,
            expected_start_time,
            expected_end_time,
            start_time,
            end_time,
        )
        return None, True

    source_path = find_source_video_path(settings, video_id)
    render_key = build_render_key_for_clip(
        settings,
        video_id,
        clip_id,
        start_time=start_time,
        end_time=end_time,
        source_path=source_path,
    )
    final_path = portrait_file_path(settings, video_id, render_key)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output.replace(final_path)
    probe = run_ffprobe(final_path, settings)
    record = PortraitRenderRecord(
        clip_id=clip_id,
        render_key=render_key,
        start_time=start_time,
        end_time=end_time,
        storage_name=final_path.name,
        width=probe.width,
        height=probe.height,
        has_audio=probe.has_audio,
    )
    commit_portrait_render(settings, video_id, record)
    return record, False


def render_portrait_for_clip_sync(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
    *,
    on_progress: ProgressCallback | None = None,
    use_cache: bool = True,
) -> PortraitRenderRecord | None:
    """Render or return a cached portrait without enqueueing a separate job.

    Returns ``None`` when the clip trim changed during rendering (stale output).
    """
    plan = build_portrait_render_plan(settings, video_id, clip_id)
    if use_cache and plan.cached_record is not None:
        on_progress and on_progress(1.0)
        return plan.cached_record

    start_time, end_time = plan.start_time, plan.end_time
    source_path = find_source_video_path(settings, video_id)
    analysis_dir = analysis_directory(settings, video_id)
    work_output = plan.output_path.with_name(f"{plan.render_key}.work.mp4")

    on_progress and on_progress(0.1)
    try:
        render_portrait_clip(
            settings,
            source_path,
            analysis_dir,
            start_time=start_time,
            end_time=end_time,
            output_path=work_output,
        )
    except Exception:
        work_output.unlink(missing_ok=True)
        work_output.with_name(f"{work_output.stem}.tmp.mp4").unlink(missing_ok=True)
        raise

    on_progress and on_progress(0.95)
    record, stale = _finalize_portrait_output(
        settings,
        video_id=video_id,
        clip_id=clip_id,
        expected_start_time=start_time,
        expected_end_time=end_time,
        temp_output=work_output,
    )
    if stale or record is None:
        return None
    on_progress and on_progress(1.0)
    return record


def run_render_portrait_clip(
    update_progress: ProgressCallback,
    context: JobExecutionContext,
) -> dict[str, object]:
    if context.clip_id is None or context.render_key is None:
        raise InvalidInputError("Portrait render job is missing clip parameters.")

    settings = context.settings
    video_id = context.video_id
    clip_id = context.clip_id
    expected_key = context.render_key

    try:
        update_progress(0.05)
        plan = build_portrait_render_plan(settings, video_id, clip_id)
        if plan.render_key != expected_key:
            raise MediaProcessingError(
                "This clip changed while the render was queued. Please try again."
            )

        update_progress(0.05)

        def clip_fraction(value: float) -> None:
            update_progress(0.05 + 0.95 * max(0.0, min(1.0, value)))

        record = render_portrait_for_clip_sync(
            settings,
            video_id,
            clip_id,
            on_progress=clip_fraction,
            use_cache=False,
        )
        update_progress(1.0)
        if record is None:
            return _job_result(None, cached=False, stale_discarded=True)
        return _job_result(record, cached=False, stale_discarded=False)
    finally:
        _release_inflight(video_id, clip_id, expected_key)


def _job_result(
    record: PortraitRenderRecord | None,
    *,
    cached: bool,
    stale_discarded: bool,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "operation": JobOperation.RENDER_PORTRAIT_CLIP.value,
        "cached": cached,
        "stale_discarded": stale_discarded,
    }
    if record is not None:
        payload.update(
            {
                "clip_id": str(record.clip_id),
                "render_key": record.render_key,
                "start_time": record.start_time,
                "end_time": record.end_time,
                "storage_name": record.storage_name,
                "width": record.width,
                "height": record.height,
                "has_audio": record.has_audio,
            }
        )
    return payload
