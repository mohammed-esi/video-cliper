"""Portrait render and stream HTTP API."""

import time
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import get_settings
from app.schemas.clip import ClipMetadata, ClipTrimUpdate
from app.schemas.job import JobOperation, JobStatus
from app.schemas.portrait import PortraitRenderRecord
from app.services.clip_storage import write_clips_manifest
from app.services.clip_trim import update_clip_trim
from app.services.portrait_clip_render import clear_portrait_inflight_for_tests
from app.services.portrait_storage import (
    build_render_key_for_clip,
    commit_portrait_render,
    portrait_file_path,
)
from tests.media_helpers import make_moving_box_video, requires_ffmpeg


def _poll_job(client, job_id: str, *, timeout_seconds: float = 30.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"completed", "failed"}:
            return body
        time.sleep(0.05)
    raise AssertionError("Job did not finish in time")


def _seed_clip(
    data_dir: Path,
    *,
    duration: float = 3.0,
    start: float = 0.5,
    end: float = 2.0,
) -> tuple[uuid.UUID, uuid.UUID]:
    settings = get_settings()
    video_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    job_dir = data_dir / "jobs" / str(video_id)
    job_dir.mkdir(parents=True)
    source = job_dir / "source.mp4"
    make_moving_box_video(source, duration=duration, box=60, start_x=40.0)
    (job_dir / "clips").mkdir()
    (job_dir / "clips" / f"{clip_id}.mp4").write_bytes(b"landscape")
    clip = ClipMetadata(
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
    write_clips_manifest(settings, video_id, [clip])
    return video_id, clip_id


def _fake_render(_settings, _source_path, _analysis_dir, *, start_time, end_time, output_path):
    duration = max(0.4, end_time - start_time)
    make_moving_box_video(
        output_path,
        size=(640, 360),
        duration=min(duration, 1.0),
        box=40,
        video_delay=0.12,
    )


@pytest.fixture(autouse=True)
def _clear_inflight() -> None:
    clear_portrait_inflight_for_tests()
    yield
    clear_portrait_inflight_for_tests()


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_post_portrait_render_returns_job_and_polls(client, data_dir) -> None:
    video_id, clip_id = _seed_clip(data_dir)
    with patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=_fake_render):
        created = client.post(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
        assert created.status_code == 202
        body = created.json()
        assert body["operation"] == JobOperation.RENDER_PORTRAIT_CLIP.value
        assert body["status"] == "queued"
        final = _poll_job(client, body["job_id"])
        assert final["status"] == "completed"
        assert final["result"]["render_key"]
        assert final["result"]["width"] > 0
        assert final["result"]["height"] > 0

    stream = client.get(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
    assert stream.status_code == 200
    assert stream.headers.get("etag", "").strip('"') == final["result"]["render_key"]
    assert "video/" in stream.headers.get("content-type", "")


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_get_portrait_supports_range_requests(client, data_dir) -> None:
    video_id, clip_id = _seed_clip(data_dir)
    with patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=_fake_render):
        created = client.post(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
        _poll_job(client, created.json()["job_id"])
        full = client.get(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
    assert full.status_code == 200
    payload = full.content
    ranged = client.get(
        f"/api/videos/{video_id}/clips/{clip_id}/portrait",
        headers={"Range": "bytes=0-99"},
    )
    assert ranged.status_code == 206
    assert ranged.content == payload[:100]
    assert ranged.headers.get("accept-ranges") == "bytes"


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_portrait_download_returns_attachment_with_cached_file(client, data_dir) -> None:
    settings = get_settings()
    video_id, clip_id = _seed_clip(data_dir)
    source = data_dir / "jobs" / str(video_id) / "source.mp4"
    render_key = build_render_key_for_clip(
        settings, video_id, clip_id, start_time=0.5, end_time=2.0, source_path=source
    )
    path = portrait_file_path(settings, video_id, render_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    make_moving_box_video(path, duration=0.5, box=40)
    commit_portrait_render(
        settings,
        video_id,
        PortraitRenderRecord(
            clip_id=clip_id,
            render_key=render_key,
            start_time=0.5,
            end_time=2.0,
            storage_name=path.name,
            width=1080,
            height=1920,
            has_audio=False,
        ),
    )

    response = client.get(
        f"/api/videos/{video_id}/clips/{clip_id}/portrait/download"
    )
    assert response.status_code == 200
    assert response.content
    disposition = response.headers.get("content-disposition", "")
    assert "attachment" in disposition.lower()
    assert ".mp4" in disposition
    assert "video/" in response.headers.get("content-type", "")


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_portrait_download_missing_before_render_returns_404(client, data_dir) -> None:
    video_id, clip_id = _seed_clip(data_dir)
    response = client.get(
        f"/api/videos/{video_id}/clips/{clip_id}/portrait/download"
    )
    assert response.status_code == 404


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_portrait_download_invalid_after_trim(client, data_dir) -> None:
    video_id, clip_id = _seed_clip(data_dir)
    settings = get_settings()
    with patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=_fake_render):
        created = client.post(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
        _poll_job(client, created.json()["job_id"])

    assert (
        client.get(f"/api/videos/{video_id}/clips/{clip_id}/portrait/download").status_code
        == 200
    )

    update_clip_trim(
        settings, video_id, clip_id, ClipTrimUpdate(start_time=0.8, end_time=2.2)
    )
    assert (
        client.get(f"/api/videos/{video_id}/clips/{clip_id}/portrait/download").status_code
        == 404
    )


def test_post_portrait_unknown_video_returns_404(client) -> None:
    response = client.post(f"/api/videos/{uuid.uuid4()}/clips/{uuid.uuid4()}/portrait")
    assert response.status_code == 404


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_post_portrait_unknown_clip_returns_404(client, data_dir) -> None:
    video_id, _ = _seed_clip(data_dir)
    response = client.post(f"/api/videos/{video_id}/clips/{uuid.uuid4()}/portrait")
    assert response.status_code == 404


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_duplicate_post_returns_same_job(client, data_dir) -> None:
    video_id, clip_id = _seed_clip(data_dir)
    with patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=_fake_render):
        first = client.post(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
        second = client.post(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
        assert first.status_code == 202
        assert second.status_code == 202
        assert first.json()["job_id"] == second.json()["job_id"]
        _poll_job(client, first.json()["job_id"])


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_cache_hit_returns_completed_job_without_queueing(client, data_dir) -> None:
    settings = get_settings()
    video_id, clip_id = _seed_clip(data_dir)
    source = data_dir / "jobs" / str(video_id) / "source.mp4"
    render_key = build_render_key_for_clip(
        settings, video_id, clip_id, start_time=0.5, end_time=2.0, source_path=source
    )
    path = portrait_file_path(settings, video_id, render_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    make_moving_box_video(path, duration=0.5, box=40)
    commit_portrait_render(
        settings,
        video_id,
        PortraitRenderRecord(
            clip_id=clip_id,
            render_key=render_key,
            start_time=0.5,
            end_time=2.0,
            storage_name=path.name,
            width=1080,
            height=1920,
            has_audio=False,
        ),
    )
    with patch(
        "app.services.portrait_clip_render.render_portrait_clip",
        side_effect=AssertionError("should not render"),
    ):
        response = client.post(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "completed"
    assert body["result"]["cached"] is True


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_get_portrait_missing_before_render_returns_404(client, data_dir) -> None:
    video_id, clip_id = _seed_clip(data_dir)
    response = client.get(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
    assert response.status_code == 404


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_trim_invalidates_portrait_stream(client, data_dir) -> None:
    video_id, clip_id = _seed_clip(data_dir)
    with patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=_fake_render):
        created = client.post(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
        _poll_job(client, created.json()["job_id"])
        assert client.get(f"/api/videos/{video_id}/clips/{clip_id}/portrait").status_code == 200

    settings = get_settings()
    update_clip_trim(
        settings, video_id, clip_id, ClipTrimUpdate(start_time=0.8, end_time=2.2)
    )
    assert client.get(f"/api/videos/{video_id}/clips/{clip_id}/portrait").status_code == 404


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_get_portrait_while_render_in_progress_returns_409(client, data_dir) -> None:
    video_id, clip_id = _seed_clip(data_dir)
    barrier = __import__("threading").Event()

    def slow_render(*_args, **_kwargs):
        barrier.set()
        time.sleep(2.0)

    with patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=slow_render):
        created = client.post(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
        assert created.status_code == 202
        assert barrier.wait(timeout=3.0)
        pending = client.get(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
        assert pending.status_code == 409
        _poll_job(client, created.json()["job_id"], timeout_seconds=10.0)


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_stale_render_completion_does_not_expose_old_trim_portrait(client, data_dir) -> None:
    video_id, clip_id = _seed_clip(data_dir)
    settings = get_settings()
    trim_applied = __import__("threading").Event()

    def slow_render(*_args, **kwargs):
        if not trim_applied.wait(timeout=3.0):
            raise AssertionError("trim did not run before render finished")
        make_moving_box_video(kwargs["output_path"], duration=0.5, box=40)

    with patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=slow_render):
        created = client.post(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
        assert created.status_code == 202
        time.sleep(0.05)
        update_clip_trim(
            settings, video_id, clip_id, ClipTrimUpdate(start_time=1.0, end_time=2.5)
        )
        trim_applied.set()
        final = _poll_job(client, created.json()["job_id"], timeout_seconds=10.0)

    assert final["status"] == "completed"
    assert final["result"]["stale_discarded"] is True
    assert client.get(f"/api/videos/{video_id}/clips/{clip_id}/portrait").status_code == 404


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_active_unrelated_job_returns_conflict(client, data_dir) -> None:
    video_id, clip_id = _seed_clip(data_dir)

    def slow_lifecycle(update_progress, _context):
        for step in (0.2, 0.4, 0.6, 0.8, 1.0):
            time.sleep(0.05)
            update_progress(step)
        return {"operation": "lifecycle_test", "message": "done"}

    with patch("app.services.job_operations._run_lifecycle_test", side_effect=slow_lifecycle):
        first = client.post(
            "/api/jobs",
            json={"video_id": str(video_id), "operation": "lifecycle_test"},
        )
        assert first.status_code == 202
        second = client.post(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
        assert second.status_code == 409


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_portrait_render_job_end_to_end_with_real_pipeline(
    client, data_dir, monkeypatch
) -> None:
    from app.services.tracking import source_analysis
    from tests.test_portrait_render import MODEL_STAND_IN, BoxDetector

    monkeypatch.setattr(source_analysis, "YuNetFaceDetector", BoxDetector)
    model = data_dir / "model.onnx"
    model.write_bytes(MODEL_STAND_IN)

    video_id, clip_id = _seed_clip(data_dir, start=0.4, end=2.0)
    source = data_dir / "jobs" / str(video_id) / "source.mp4"
    make_moving_box_video(
        source,
        duration=3.0,
        box=80,
        start_x=100.0,
        speed_px_per_second=200.0,
        video_delay=0.12,
    )
    created = client.post(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
    assert created.status_code == 202
    final = _poll_job(client, created.json()["job_id"], timeout_seconds=120.0)
    assert final["status"] == "completed"
    assert final["result"]["width"] == 1080
    assert final["result"]["height"] == 1920
    assert final["result"]["has_audio"] is True

    stream = client.get(f"/api/videos/{video_id}/clips/{clip_id}/portrait")
    assert stream.status_code == 200
    assert len(stream.content) > 1024
