import uuid

from pydantic import BaseModel, Field, model_validator


class ClipMetadata(BaseModel):
    clip_id: uuid.UUID
    video_id: uuid.UUID
    start_time: float = Field(ge=0.0)
    end_time: float = Field(gt=0.0)
    duration: float = Field(gt=0.0)
    generated_start_time: float = Field(ge=0.0)
    generated_end_time: float = Field(gt=0.0)
    storage_name: str = Field(max_length=128)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    has_audio: bool

    @model_validator(mode="before")
    @classmethod
    def default_generated_bounds(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        start = data.get("start_time")
        end = data.get("end_time")
        if "generated_start_time" not in data and start is not None:
            data = {**data, "generated_start_time": start}
        if "generated_end_time" not in data and end is not None:
            data = {**data, "generated_end_time": end}
        return data


class ClipsManifestFile(BaseModel):
    video_id: uuid.UUID
    clips: list[ClipMetadata]


class ClipListResponse(BaseModel):
    video_id: uuid.UUID
    source_duration_seconds: float = Field(gt=0.0)
    clips: list[ClipMetadata]


class ClipTrimUpdate(BaseModel):
    start_time: float = Field(ge=0.0)
    end_time: float = Field(gt=0.0)

    @model_validator(mode="after")
    def end_after_start(self) -> "ClipTrimUpdate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")
        return self
