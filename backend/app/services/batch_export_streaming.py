from uuid import UUID

from starlette.responses import FileResponse

from app.core.config import Settings
from app.services.batch_export import (
    batch_export_download_filename,
    validate_batch_export_download,
)
from app.services.video_streaming import media_type_for_path


def build_batch_export_download_response(
    settings: Settings,
    video_id: UUID,
    job_id: UUID,
) -> FileResponse:
    path = validate_batch_export_download(settings, video_id, job_id)
    return FileResponse(
        path=path,
        media_type=media_type_for_path(path) or "application/zip",
        filename=batch_export_download_filename(job_id),
        content_disposition_type="attachment",
        headers={"Cache-Control": "private, no-cache, must-revalidate"},
    )
