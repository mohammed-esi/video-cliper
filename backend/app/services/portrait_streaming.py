import re
import uuid
from pathlib import Path

from starlette.responses import FileResponse

from app.core.config import Settings
from app.core.errors import NotFoundError, PortraitNotReadyError
from app.schemas.portrait import PortraitRenderRecord
from app.services.portrait_clip_render import get_inflight_portrait_job
from app.services.portrait_storage import current_portrait_record, portrait_file_path
from app.services.video_streaming import media_type_for_path

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def portrait_export_filename(record: PortraitRenderRecord) -> str:
    short_id = str(record.clip_id).split("-", maxsplit=1)[0]
    stem = f"clip-{short_id}_{record.start_time:.1f}-{record.end_time:.1f}"
    safe = _SAFE_FILENAME.sub("-", stem).strip("-") or "clip"
    return f"{safe}.mp4"


def build_portrait_video_response(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
) -> FileResponse:
    record = _require_current_portrait(settings, video_id, clip_id)
    path = portrait_file_path(settings, video_id, record.render_key)
    return _portrait_file_response(
        path,
        record.render_key,
        download_name=portrait_export_filename(record),
        attachment=False,
    )


def build_portrait_download_response(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
) -> FileResponse:
    record = _require_current_portrait(settings, video_id, clip_id)
    path = portrait_file_path(settings, video_id, record.render_key)
    return _portrait_file_response(
        path,
        record.render_key,
        download_name=portrait_export_filename(record),
        attachment=True,
    )


def _require_current_portrait(
    settings: Settings,
    video_id: uuid.UUID,
    clip_id: uuid.UUID,
) -> PortraitRenderRecord:
    record = current_portrait_record(settings, video_id, clip_id)
    if record is not None:
        return record

    if get_inflight_portrait_job(settings, video_id, clip_id) is not None:
        raise PortraitNotReadyError(
            "Portrait rendering is in progress for this clip. Poll the processing job."
        )
    raise NotFoundError("No portrait is available for this clip yet.")


def _portrait_file_response(
    path: Path,
    render_key: str,
    *,
    download_name: str,
    attachment: bool,
) -> FileResponse:
    return FileResponse(
        path=path,
        media_type=media_type_for_path(path),
        filename=download_name,
        content_disposition_type="attachment" if attachment else "inline",
        headers={
            "Cache-Control": "private, no-cache, must-revalidate",
            "ETag": f'"{render_key}"',
        },
    )
