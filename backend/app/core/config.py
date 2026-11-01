from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Video Clipper API"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
    )

    data_dir: Path = Path("data")
    max_upload_bytes: int = 500 * 1024 * 1024
    max_duration_seconds: float = 7200.0
    max_video_width: int = 3840
    max_video_height: int = 3840
    ffprobe_path: str = "ffprobe"
    ffmpeg_path: str = "ffmpeg"
    ffprobe_timeout_seconds: float = 60.0
    upload_chunk_size_bytes: int = 1024 * 1024
    youtube_download_timeout_seconds: float = 600.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
