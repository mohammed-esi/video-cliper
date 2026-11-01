import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.paths import processing_job_file, processing_jobs_dir
from app.schemas.job import JobOperation, JobStatus


class StoredJob(BaseModel):
    job_id: uuid.UUID
    video_id: uuid.UUID
    operation: JobOperation
    status: JobStatus
    progress: float = Field(ge=0.0, le=1.0, default=0.0)
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
    result: dict[str, Any] | None = None
    clip_id: uuid.UUID | None = None
    render_key: str | None = None
    batch_clip_ids: list[uuid.UUID] | None = None
    batch_trim_revisions: dict[str, str] | None = None


def ensure_processing_jobs_dir(settings: Settings) -> Path:
    directory = processing_jobs_dir(settings.data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def write_job(settings: Settings, job: StoredJob) -> None:
    ensure_processing_jobs_dir(settings)
    path = processing_job_file(settings.data_dir, job.job_id)
    payload = job.model_dump(mode="json")
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def read_job(settings: Settings, job_id: uuid.UUID) -> StoredJob | None:
    path = processing_job_file(settings.data_dir, job_id)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return StoredJob.model_validate(data)


def list_jobs(settings: Settings) -> list[StoredJob]:
    directory = ensure_processing_jobs_dir(settings)
    jobs: list[StoredJob] = []
    for path in directory.glob("*.json"):
        if path.name.endswith(".tmp"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            jobs.append(StoredJob.model_validate(data))
        except (json.JSONDecodeError, ValueError):
            continue
    return jobs


def utc_now() -> datetime:
    return datetime.now(tz=UTC)
