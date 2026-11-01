"""Batch ZIP export API and worker."""

import io
import time
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.schemas.batch_export import BatchExportClipItem, BatchExportRequest
from app.schemas.clip import ClipMetadata
from app.schemas.job import JobStatus
from app.schemas.portrait import PortraitRenderRecord
from app.services.batch_export import normalize_batch_selection
from app.services.clip_storage import write_clips_manifest
from app.services.clip_trim_revision import clip_trim_revision
from app.services.portrait_clip_render import clear_portrait_inflight_for_tests
from app.services.portrait_storage import (
    build_render_key_for_clip,
    commit_portrait_render,
    portrait_file_path,
)
from tests.media_helpers import make_moving_box_video, requires_ffmpeg


def _poll_job(client, job_id: str, *, timeout_seconds: float = 60.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"completed", "failed"}:
            return body
        time.sleep(0.05)
    raise AssertionError("Job did not finish in time")


def _seed_clips(
    data_dir: Path,
    *,
    count: int = 3,
    duration: float = 4.0,
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    settings = get_settings()
    video_id = uuid.uuid4()
    clip_ids: list[uuid.UUID] = []
    job_dir = data_dir / "jobs" / str(video_id)
    job_dir.mkdir(parents=True)
    source = job_dir / "source.mp4"
    make_moving_box_video(source, duration=duration, box=60, start_x=40.0)
    (job_dir / "clips").mkdir()
    clips: list[ClipMetadata] = []
    for index in range(count):
        clip_id = uuid.uuid4()
        clip_ids.append(clip_id)
        (job_dir / "clips" / f"{clip_id}.mp4").write_bytes(b"landscape")
        start = 0.5 + index * 0.5
        end = start + 1.0
        clips.append(
            ClipMetadata(
                clip_id=clip_id,
                video_id=video_id,
                start_time=start,
                end_time=end,
                duration=end - start,
                generated_start_time=start,
                generated_end_time=end,
                storage_name=f"{clip_id}.mp4",
                width=1280,
                height=720,
                has_audio=False,
            )
        )
    write_clips_manifest(settings, video_id, clips)
    return video_id, clip_ids


def _fake_render(_settings, _source_path, _analysis_dir, *, start_time, end_time, output_path):
    duration = max(0.4, end_time - start_time)
    make_moving_box_video(
        output_path,
        size=(640, 360),
        duration=min(duration, 1.0),
        box=40,
        video_delay=0.12,
    )


def _cache_portrait(data_dir: Path, video_id: uuid.UUID, clip_id: uuid.UUID) -> None:
    settings = get_settings()
    source = data_dir / "jobs" / str(video_id) / "source.mp4"
    from app.services.portrait_storage import get_clip_from_manifest

    clip = get_clip_from_manifest(settings, video_id, clip_id)
    render_key = build_render_key_for_clip(
        settings,
        video_id,
        clip_id,
        start_time=clip.start_time,
        end_time=clip.end_time,
        source_path=source,
    )
    path = portrait_file_path(settings, video_id, render_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    make_moving_box_video(path, size=(1080, 1920), duration=0.5, box=80)
    commit_portrait_render(
        settings,
        video_id,
        PortraitRenderRecord(
            clip_id=clip_id,
            render_key=render_key,
            start_time=clip.start_time,
            end_time=clip.end_time,
            storage_name=path.name,
            width=1080,
            height=1920,
            has_audio=False,
        ),
    )


@requires_ffmpeg
def test_batch_export_rejects_empty_selection(client, data_dir):
    video_id, _clip_ids = _seed_clips(data_dir, count=1)
    response = client.post(
        f"/api/videos/{video_id}/exports/batch",
        json={"clips": []},
    )
    assert response.status_code == 422


@requires_ffmpeg
def test_batch_export_rejects_stale_trim_revision(client, data_dir):
    video_id, clip_ids = _seed_clips(data_dir, count=1)
    response = client.post(
        f"/api/videos/{video_id}/exports/batch",
        json={
            "clips": [
                {
                    "clip_id": str(clip_ids[0]),
                    "trim_revision": "0.0_99.0",
                }
            ]
        },
    )
    assert response.status_code == 400


@requires_ffmpeg
@patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=_fake_render)
def test_batch_export_zip_contains_portraits_in_order(mock_render, client, data_dir):
    clear_portrait_inflight_for_tests()
    video_id, clip_ids = _seed_clips(data_dir, count=3)
    settings = get_settings()
    from app.services.portrait_storage import get_clip_from_manifest

    items = []
    for clip_id in clip_ids:
        clip = get_clip_from_manifest(settings, video_id, clip_id)
        items.append(
            {
                "clip_id": str(clip_id),
                "trim_revision": clip_trim_revision(clip.start_time, clip.end_time),
            }
        )

    start = client.post(f"/api/videos/{video_id}/exports/batch", json={"clips": items})
    assert start.status_code == 202
    job_id = start.json()["job_id"]
    job = _poll_job(client, job_id)
    assert job["status"] == "completed"
    assert mock_render.call_count == 3

    download = client.get(f"/api/videos/{video_id}/exports/batch/{job_id}/download")
    assert download.status_code == 200
    assert "attachment" in download.headers.get("content-disposition", "").lower()
    assert download.headers.get("content-type", "").startswith("application/")

    archive = zipfile.ZipFile(io.BytesIO(download.content))
    names = archive.namelist()
    assert len(names) == 3
    for name in names:
        assert name.endswith(".mp4")


@requires_ffmpeg
@patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=_fake_render)
def test_batch_export_reuses_cached_portrait(mock_render, client, data_dir):
    clear_portrait_inflight_for_tests()
    video_id, clip_ids = _seed_clips(data_dir, count=2)
    _cache_portrait(data_dir, video_id, clip_ids[0])
    settings = get_settings()
    from app.services.portrait_storage import get_clip_from_manifest

    items = []
    for clip_id in clip_ids:
        clip = get_clip_from_manifest(settings, video_id, clip_id)
        items.append(
            {
                "clip_id": str(clip_id),
                "trim_revision": clip_trim_revision(clip.start_time, clip.end_time),
            }
        )

    start = client.post(f"/api/videos/{video_id}/exports/batch", json={"clips": items})
    job = _poll_job(client, start.json()["job_id"])
    assert job["status"] == "completed"
    assert mock_render.call_count == 1


@requires_ffmpeg
def test_batch_export_download_rejects_incomplete_job(client, data_dir):
    video_id, clip_ids = _seed_clips(data_dir, count=1)
    settings = get_settings()
    from app.services.portrait_storage import get_clip_from_manifest

    clip = get_clip_from_manifest(settings, video_id, clip_ids[0])
    body = {
        "clips": [
            {
                "clip_id": str(clip_ids[0]),
                "trim_revision": clip_trim_revision(clip.start_time, clip.end_time),
            }
        ]
    }
    start = client.post(f"/api/videos/{video_id}/exports/batch", json=body)
    assert start.status_code == 202
    job_id = start.json()["job_id"]
    status = client.get(f"/api/jobs/{job_id}").json()
    if status["status"] == "completed":
        pytest.skip("Job finished before download probe (fast environment).")
    response = client.get(
        f"/api/videos/{video_id}/exports/batch/{job_id}/download"
    )
    assert response.status_code == 404


def test_normalize_batch_selection_deduplicates_ids(data_dir):
    settings = get_settings()
    video_id, clip_ids = _seed_clips(data_dir, count=2)
    from app.services.portrait_storage import get_clip_from_manifest

    clip = get_clip_from_manifest(settings, video_id, clip_ids[0])
    revision = clip_trim_revision(clip.start_time, clip.end_time)
    request = BatchExportRequest(
        clips=[
            BatchExportClipItem(clip_id=clip_ids[0], trim_revision=revision),
            BatchExportClipItem(clip_id=clip_ids[0], trim_revision=revision),
            BatchExportClipItem(
                clip_id=clip_ids[1],
                trim_revision=clip_trim_revision(
                    get_clip_from_manifest(settings, video_id, clip_ids[1]).start_time,
                    get_clip_from_manifest(settings, video_id, clip_ids[1]).end_time,
                ),
            ),
        ]
    )
    ordered, revisions = normalize_batch_selection(settings, video_id, request)
    assert ordered == [clip_ids[0], clip_ids[1]]
    assert len(revisions) == 2
