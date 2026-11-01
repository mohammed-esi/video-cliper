import threading
import uuid
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.errors import JobQueueFullError
from app.schemas.job import CreateJobRequest, JobOperation
from app.services import job_manager


def _seed_video(data_dir: Path) -> uuid.UUID:
    video_id = uuid.uuid4()
    directory = data_dir / "jobs" / str(video_id)
    directory.mkdir(parents=True)
    (directory / "source.mp4").write_bytes(b"\x00" * 64)
    return video_id


def test_concurrent_create_job_respects_queue_limit(data_dir, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("MAX_PROCESSING_QUEUE_SIZE", "2")
    get_settings.cache_clear()
    settings = get_settings()
    job_manager.initialize(settings)

    video_ids = [_seed_video(data_dir) for _ in range(4)]
    barrier = threading.Barrier(4)
    results: list[Exception | None] = [None] * 4

    def worker(index: int) -> None:
        try:
            barrier.wait(timeout=2.0)
            job_manager.create_job(
                CreateJobRequest(
                    video_id=video_ids[index],
                    operation=JobOperation.LIFECYCLE_TEST,
                )
            )
        except Exception as exc:
            results[index] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5.0)

    queue_errors = [result for result in results if isinstance(result, JobQueueFullError)]
    assert len(queue_errors) >= 1
    get_settings.cache_clear()
