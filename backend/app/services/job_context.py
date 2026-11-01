import uuid
from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class JobExecutionContext:
    job_id: uuid.UUID
    video_id: uuid.UUID
    settings: Settings
    clip_id: uuid.UUID | None = None
    render_key: str | None = None
