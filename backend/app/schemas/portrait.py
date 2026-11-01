import uuid

from pydantic import BaseModel, Field


class PortraitRenderRecord(BaseModel):
    clip_id: uuid.UUID
    render_key: str = Field(min_length=8, max_length=128)
    start_time: float = Field(ge=0.0)
    end_time: float = Field(gt=0.0)
    storage_name: str = Field(min_length=4, max_length=128)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    has_audio: bool


class PortraitsManifestFile(BaseModel):
    video_id: uuid.UUID
    renders: list[PortraitRenderRecord] = Field(default_factory=list)
