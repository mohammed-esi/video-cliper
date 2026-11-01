import uuid

from pydantic import BaseModel, Field


class VideoUploadResponse(BaseModel):
    video_id: uuid.UUID
    original_filename: str = Field(max_length=255)
    duration_seconds: float = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    has_audio: bool
    container: str = Field(max_length=64)


class YouTubeImportRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class ErrorResponse(BaseModel):
    message: str
