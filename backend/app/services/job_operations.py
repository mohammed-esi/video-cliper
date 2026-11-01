import logging
import time
from collections.abc import Callable
from typing import Any

from app.schemas.job import JobOperation
from app.services.job_context import JobExecutionContext

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float], None]
OperationHandler = Callable[[ProgressCallback, JobExecutionContext], dict[str, Any]]


def _run_lifecycle_test(
    update_progress: ProgressCallback,
    _context: JobExecutionContext,
) -> dict[str, Any]:
    """Test-only operation: simulates work without clip generation."""
    steps = 5
    for index in range(steps):
        time.sleep(0.02)
        update_progress((index + 1) / steps)
    return {
        "operation": JobOperation.LIFECYCLE_TEST.value,
        "message": "Lifecycle test completed successfully.",
    }


def _run_lifecycle_test_fail(
    _update_progress: ProgressCallback,
    _context: JobExecutionContext,
) -> dict[str, Any]:
    raise RuntimeError("Simulated processing failure.")


def _run_generate_clips(
    update_progress: ProgressCallback,
    context: JobExecutionContext,
) -> dict[str, Any]:
    from app.services.clip_generation import run_generate_clips

    return run_generate_clips(update_progress, context)


def _run_render_portrait_clip(
    update_progress: ProgressCallback,
    context: JobExecutionContext,
) -> dict[str, Any]:
    from app.services.portrait_clip_render import run_render_portrait_clip

    return run_render_portrait_clip(update_progress, context)


def _run_batch_export_clips(
    update_progress: ProgressCallback,
    context: JobExecutionContext,
) -> dict[str, Any]:
    from app.services.batch_export import run_batch_export_clips

    return run_batch_export_clips(update_progress, context)


_OPERATION_HANDLERS: dict[JobOperation, OperationHandler] = {
    JobOperation.LIFECYCLE_TEST: _run_lifecycle_test,
    JobOperation.GENERATE_CLIPS: _run_generate_clips,
    JobOperation.RENDER_PORTRAIT_CLIP: _run_render_portrait_clip,
    JobOperation.BATCH_EXPORT_CLIPS: _run_batch_export_clips,
}


def get_operation_handler(operation: JobOperation) -> OperationHandler:
    handler = _OPERATION_HANDLERS.get(operation)
    if handler is None:
        raise ValueError(f"Unsupported operation: {operation}")
    return handler


def register_test_failure_handler() -> None:
    """Used by tests to simulate worker failures."""
    _OPERATION_HANDLERS[JobOperation.LIFECYCLE_TEST] = _run_lifecycle_test_fail


def restore_default_handlers() -> None:
    _OPERATION_HANDLERS[JobOperation.LIFECYCLE_TEST] = _run_lifecycle_test
