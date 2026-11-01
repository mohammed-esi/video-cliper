import json
import time
import uuid
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.errors import JobQueueFullError
from app.core.paths import processing_job_file
from app.schemas.job import CreateJobRequest, JobOperation, JobStatus
from app.services import job_manager
from app.services.job_operations import register_test_failure_handler, restore_default_handlers
from app.services.job_persistence import StoredJob, utc_now, write_job


def _seed_video(data_dir: Path, video_id: uuid.UUID | None = None) -> uuid.UUID:
    video_id = video_id or uuid.uuid4()
    directory = data_dir / "jobs" / str(video_id)
    directory.mkdir(parents=True)
    (directory / "source.mp4").write_bytes(b"\x00" * 64)
    return video_id


def test_create_job_returns_202_and_completes(client, data_dir) -> None:
    video_id = _seed_video(data_dir)
    response = client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "lifecycle_test"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["operation"] == "lifecycle_test"

    job_id = body["job_id"]
    final = None
    for _ in range(100):
        poll = client.get(f"/api/jobs/{job_id}")
        assert poll.status_code == 200
        final = poll.json()
        if final["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert final is not None
    assert final["status"] == "completed"
    assert final["progress"] == 1.0
    assert final["result"]["operation"] == "lifecycle_test"


def test_create_job_unknown_video_returns_404(client, data_dir) -> None:
    response = client.post(
        "/api/jobs",
        json={"video_id": str(uuid.uuid4()), "operation": "lifecycle_test"},
    )
    assert response.status_code == 404


def test_get_unknown_job_returns_404(client) -> None:
    response = client.get(f"/api/jobs/{uuid.uuid4()}")
    assert response.status_code == 404


def test_duplicate_processing_request_returns_409(client, data_dir) -> None:
    video_id = _seed_video(data_dir)
    first = client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "lifecycle_test"},
    )
    assert first.status_code == 202
    second = client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "lifecycle_test"},
    )
    assert second.status_code == 409


def test_worker_failure_marks_job_failed(client, data_dir) -> None:
    video_id = _seed_video(data_dir)
    register_test_failure_handler()
    try:
        created = client.post(
            "/api/jobs",
            json={"video_id": str(video_id), "operation": "lifecycle_test"},
        )
        job_id = created.json()["job_id"]
        final = None
        for _ in range(100):
            poll = client.get(f"/api/jobs/{job_id}")
            final = poll.json()
            if final["status"] == "failed":
                break
            time.sleep(0.05)
        assert final is not None
        assert final["status"] == "failed"
        assert final["error_message"]
    finally:
        restore_default_handlers()


def test_interrupted_job_marked_failed_on_restart(data_dir, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    settings = get_settings()

    video_id = _seed_video(data_dir)
    job_id = uuid.uuid4()
    now = utc_now()
    stale = StoredJob(
        job_id=job_id,
        video_id=video_id,
        operation=JobOperation.LIFECYCLE_TEST,
        status=JobStatus.PROCESSING,
        progress=0.5,
        created_at=now,
        updated_at=now,
    )
    write_job(settings, stale)

    job_manager.initialize(settings)
    recovered = job_manager.get_job(job_id)
    assert recovered.status == JobStatus.FAILED
    assert "interrupted" in (recovered.error_message or "").lower()

    persisted = json.loads(processing_job_file(settings.data_dir, job_id).read_text())
    assert persisted["status"] == "failed"


def test_terminal_job_state_cannot_be_overwritten(data_dir, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    settings = get_settings()
    job_manager.initialize(settings)

    video_id = _seed_video(data_dir)
    created = job_manager.create_job(
        CreateJobRequest(video_id=video_id, operation=JobOperation.LIFECYCLE_TEST)
    )
    job_manager._update_job(
        created.job_id,
        status=JobStatus.FAILED,
        error_message="Interrupted.",
        progress=0.0,
    )
    job_manager._update_job(
        created.job_id,
        status=JobStatus.COMPLETED,
        progress=1.0,
        result={"ok": True},
    )
    final = job_manager.get_job(created.job_id)
    assert final.status == JobStatus.FAILED
    assert final.error_message == "Interrupted."
    get_settings.cache_clear()


def test_create_job_enforces_queue_limit(data_dir, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("MAX_PROCESSING_QUEUE_SIZE", "1")
    get_settings.cache_clear()
    settings = get_settings()
    job_manager.initialize(settings)

    video_a = _seed_video(data_dir)
    video_b = _seed_video(data_dir)
    job_manager.create_job(
        CreateJobRequest(video_id=video_a, operation=JobOperation.LIFECYCLE_TEST)
    )
    with pytest.raises(JobQueueFullError):
        job_manager.create_job(
            CreateJobRequest(video_id=video_b, operation=JobOperation.LIFECYCLE_TEST)
        )
    get_settings.cache_clear()


def test_job_metadata_persisted_to_disk(client, data_dir) -> None:
    video_id = _seed_video(data_dir)
    settings = get_settings()
    created = client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "lifecycle_test"},
    )
    job_id = uuid.UUID(created.json()["job_id"])
    path = processing_job_file(settings.data_dir, job_id)
    assert path.is_file()
