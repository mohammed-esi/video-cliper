import uuid

from pydantic import BaseModel, Field


class BatchExportClipItem(BaseModel):
    clip_id: uuid.UUID
    trim_revision: str = Field(min_length=1, max_length=64)


class BatchExportRequest(BaseModel):
    clips: list[BatchExportClipItem] = Field(min_length=1, max_length=200)
