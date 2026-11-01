import logging
import threading
from concurrent import futures
from uuid import UUID

from app.core.config import Settings
from app.services import job_manager
from app.services import ffmpeg_runner

logger = logging.getLogger(__name__)

_executor: futures.ThreadPoolExecutor | None = None
_shutdown_event = threading.Event()


def is_shutdown_requested() -> bool:
    return _shutdown_event.is_set()


def start(settings: Settings) -> None:
    global _executor
    if _executor is not None:
        return
    _shutdown_event.clear()
    job_manager.initialize(settings)
    _executor = futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="processing")
    logger.info("Processing worker started (single-thread executor).")


def shutdown() -> None:
    global _executor
    _shutdown_event.set()
    ffmpeg_runner.terminate_active_process()
    if _executor is None:
        return
    _executor.shutdown(wait=False, cancel_futures=True)
    _executor = None
    logger.info("Processing worker shut down.")


def submit_job(job_id: UUID) -> None:
    if _executor is None:
        raise RuntimeError("Processing worker is not running.")
    _executor.submit(job_manager.run_job, job_id)
