import asyncio

from fastapi import APIRouter, File, Request, UploadFile

from app.core.config import Settings, get_settings
from app.schemas.video import VideoUploadResponse, YouTubeImportRequest
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
