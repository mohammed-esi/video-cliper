import asyncio
from uuid import UUID

from fastapi import APIRouter, status

from app.core.config import get_settings
from app.schemas.job import CreateJobRequest, JobResponse
from app.services import job_manager
from app.services.processing_worker import submit_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a video processing job",
)
async def create_job(body: CreateJobRequest) -> JobResponse:
    get_settings()
    response = await asyncio.to_thread(job_manager.create_job, body)
    await asyncio.to_thread(submit_job, response.job_id)
    return response


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get processing job status",
)
async def get_job(job_id: UUID) -> JobResponse:
    get_settings()
    return await asyncio.to_thread(job_manager.get_job, job_id)
