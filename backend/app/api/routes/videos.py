import asyncio
from uuid import UUID

from fastapi import APIRouter, File, Request, UploadFile, status

from app.core.config import Settings, get_settings
from app.schemas.batch_export import BatchExportRequest
from app.schemas.clip import ClipListResponse, ClipMetadata, ClipTrimUpdate
from app.schemas.job import JobResponse, JobStatus
from app.schemas.video import VideoUploadResponse, YouTubeImportRequest
from app.services.clip_thumbnails import build_clip_thumbnail_response
from app.services.clip_trim import list_clips_with_source_duration, update_clip_trim
from app.services.batch_export import start_batch_export_job
from app.services.batch_export_streaming import build_batch_export_download_response
from app.services.portrait_clip_render import request_portrait_render
from app.services.portrait_streaming import (
    build_portrait_download_response,
    build_portrait_video_response,
)
from app.services.processing_worker import submit_job
from app.services.video_streaming import build_clip_video_response, build_source_video_response
from app.services.video_upload import accept_video_upload
from app.services.youtube_download import import_youtube_video
from app.services.youtube_urls import parse_youtube_url

router = APIRouter(prefix="/videos", tags=["videos"])


def _import_youtube_sync(url: str, settings: Settings) -> VideoUploadResponse:
    parsed = parse_youtube_url(url)
    return import_youtube_video(parsed, settings)


@router.post(
    "/upload",
    response_model=VideoUploadResponse,
    status_code=201,
    summary="Upload and validate a source video",
)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
) -> VideoUploadResponse:
    settings = get_settings()
    return await accept_video_upload(file, request, settings)


@router.post(
    "/youtube",
    response_model=VideoUploadResponse,
    status_code=201,
    summary="Import a video from YouTube",
)
async def import_youtube(body: YouTubeImportRequest) -> VideoUploadResponse:
    settings = get_settings()
    return await asyncio.to_thread(_import_youtube_sync, body.url, settings)


@router.get(
    "/{video_id}/source",
    summary="Stream imported source video (local assessment use)",
    responses={
        200: {"description": "Full file"},
        206: {"description": "Partial content (Range request)"},
    },
)
async def stream_source_video(video_id: UUID):
    """Serves the validated source file for browser playback. No auth — local tool only."""
    settings = get_settings()
    return await asyncio.to_thread(build_source_video_response, settings, video_id)


@router.get(
    "/{video_id}/clips",
    response_model=ClipListResponse,
    summary="List generated clips for a video",
)
async def list_video_clips(video_id: UUID) -> ClipListResponse:
    settings = get_settings()
    return await asyncio.to_thread(list_clips_with_source_duration, settings, video_id)


@router.patch(
    "/{video_id}/clips/{clip_id}",
    response_model=ClipMetadata,
    summary="Update clip trim boundaries on the source timeline",
)
async def patch_clip_trim(
    video_id: UUID,
    clip_id: UUID,
    body: ClipTrimUpdate,
) -> ClipMetadata:
    settings = get_settings()
    return await asyncio.to_thread(
        update_clip_trim,
        settings,
        video_id,
        clip_id,
        body,
    )


@router.post(
    "/{video_id}/clips/{clip_id}/portrait",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue portrait rendering for a clip (uses saved trim range)",
)
async def request_clip_portrait_render(video_id: UUID, clip_id: UUID) -> JobResponse:
    settings = get_settings()

    def work() -> JobResponse:
        response = request_portrait_render(settings, video_id, clip_id)
        if response.status == JobStatus.QUEUED:
            submit_job(response.job_id)
        return response

    return await asyncio.to_thread(work)


@router.get(
    "/{video_id}/clips/{clip_id}/portrait",
    summary="Stream the current 9:16 portrait MP4 for a clip (local assessment use)",
    responses={
        200: {"description": "Full file"},
        206: {"description": "Partial content (Range request)"},
        404: {"description": "Portrait not available for the current trim"},
        409: {"description": "Portrait render in progress"},
    },
)
async def stream_clip_portrait_video(video_id: UUID, clip_id: UUID):
    settings = get_settings()
    return await asyncio.to_thread(
        build_portrait_video_response, settings, video_id, clip_id
    )


@router.post(
    "/{video_id}/exports/batch",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue batch ZIP export for selected clips",
)
async def request_batch_clip_export(
    video_id: UUID,
    body: BatchExportRequest,
) -> JobResponse:
    settings = get_settings()

    def work() -> JobResponse:
        response = start_batch_export_job(settings, video_id, body)
        if response.status == JobStatus.QUEUED:
            submit_job(response.job_id)
        return response

    return await asyncio.to_thread(work)


@router.get(
    "/{video_id}/exports/batch/{job_id}/download",
    summary="Download a completed batch export ZIP",
    responses={
        200: {"description": "ZIP attachment"},
        404: {"description": "Export missing, incomplete, or outdated"},
    },
)
async def download_batch_clip_export(video_id: UUID, job_id: UUID):
    settings = get_settings()
    return await asyncio.to_thread(
        build_batch_export_download_response,
        settings,
        video_id,
        job_id,
    )


@router.get(
    "/{video_id}/clips/{clip_id}/portrait/download",
    summary="Download the current 9:16 portrait MP4 for a clip",
    responses={
        200: {"description": "Portrait MP4 attachment"},
        404: {"description": "Portrait not available for the current trim"},
        409: {"description": "Portrait render in progress"},
    },
)
async def download_clip_portrait_video(video_id: UUID, clip_id: UUID):
    settings = get_settings()
    return await asyncio.to_thread(
        build_portrait_download_response, settings, video_id, clip_id
    )


@router.get(
    "/{video_id}/clips/{clip_id}/thumbnail",
    summary="Clip thumbnail from the source video at the edited range midpoint",
    responses={
        200: {"content": {"image/jpeg": {}}},
    },
)
async def get_clip_thumbnail(video_id: UUID, clip_id: UUID):
    settings = get_settings()
    return await asyncio.to_thread(
        build_clip_thumbnail_response,
        settings,
        video_id,
        clip_id,
    )


@router.get(
    "/{video_id}/clips/{clip_id}",
    summary="Stream a generated clip (local assessment use)",
    responses={
        200: {"description": "Full file"},
        206: {"description": "Partial content (Range request)"},
    },
)
async def stream_clip_video(video_id: UUID, clip_id: UUID):
    settings = get_settings()
    return await asyncio.to_thread(build_clip_video_response, settings, video_id, clip_id)
