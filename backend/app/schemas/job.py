import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobOperation(StrEnum):
    LIFECYCLE_TEST = "lifecycle_test"
    GENERATE_CLIPS = "generate_clips"
    RENDER_PORTRAIT_CLIP = "render_portrait_clip"
    BATCH_EXPORT_CLIPS = "batch_export_clips"


class CreateJobRequest(BaseModel):
    video_id: uuid.UUID
    operation: JobOperation
    clip_id: uuid.UUID | None = None
    render_key: str | None = None


class JobResponse(BaseModel):
    job_id: uuid.UUID
    video_id: uuid.UUID
    operation: JobOperation
    status: JobStatus
    progress: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
    result: dict[str, Any] | None = None
