import mimetypes
import uuid
from pathlib import Path

from starlette.responses import FileResponse

from app.core.config import Settings
from app.services.clip_storage import find_clip_file
from app.services.video_storage import find_source_video_path


def media_type_for_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def build_source_video_response(settings: Settings, video_id: uuid.UUID) -> FileResponse:
    source_path = find_source_video_path(settings, video_id)
    return FileResponse(
        path=source_path,
        media_type=media_type_for_path(source_path),
        filename=f"source{source_path.suffix}",
    )


def build_clip_video_response(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
) -> FileResponse:
    clip_path = find_clip_file(settings, video_id, clip_id)
    return FileResponse(
        path=clip_path,
        media_type=media_type_for_path(clip_path),
        filename=f"clip-{clip_id}.mp4",
    )
