import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.errors import MediaProcessingError
from app.main import create_app
from app.services import clip_generation
from app.services import clip_storage
from app.services.clip_storage import clips_directory, read_clips_manifest
from app.services.ffprobe import run_ffprobe


pytestmark_ffmpeg = pytest.mark.ffmpeg


@pytest.fixture
def clip_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CLIP_TARGET_DURATION_SECONDS", "1")
    monkeypatch.setenv("CLIP_MIN_TAIL_MERGE_SECONDS", "0.5")
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_test_mp4(path: Path, duration: float = 2.5) -> None:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=640x360:rate=30",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=44100",
        "-t",
        str(duration),
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        "-y",
        str(path),
    ]
    subprocess.run(command, check=True, timeout=60)


def _poll_job(client, job_id: str, *, timeout_seconds: float = 30.0) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"completed", "failed"}:
            return body
        time.sleep(0.1)
    raise AssertionError("Job did not finish in time")


@pytest.mark.ffmpeg
@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg/ffprobe not installed")
def test_generate_clips_job_completes_with_metadata(clip_client, tmp_path) -> None:
    data_dir = tmp_path
    video_id = uuid.uuid4()
    directory = data_dir / "jobs" / str(video_id)
    directory.mkdir(parents=True)
    source = directory / "source.mp4"
    _make_test_mp4(source, duration=2.5)

    created = clip_client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "generate_clips"},
    )
    assert created.status_code == 202
    final = _poll_job(clip_client, created.json()["job_id"])
    assert final["status"] == "completed"
    assert final["result"]["clip_count"] >= 2

    listing = clip_client.get(f"/api/videos/{video_id}/clips")
    assert listing.status_code == 200
    clips = listing.json()["clips"]
    assert len(clips) == final["result"]["clip_count"]

    first_clip_id = clips[0]["clip_id"]
    stream = clip_client.get(f"/api/videos/{video_id}/clips/{first_clip_id}")
    assert stream.status_code == 200
    assert stream.content


@pytest.mark.ffmpeg
@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg/ffprobe not installed")
def test_clip_playback_supports_range(clip_client, tmp_path) -> None:
    data_dir = tmp_path
    video_id = uuid.uuid4()
    directory = data_dir / "jobs" / str(video_id)
    directory.mkdir(parents=True)
    _make_test_mp4(directory / "source.mp4", duration=2.0)

    created = clip_client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "generate_clips"},
    )
    final = _poll_job(clip_client, created.json()["job_id"])
    assert final["status"] == "completed"

    manifest = read_clips_manifest(get_settings(), video_id)
    clip_id = manifest.clips[0].clip_id
    response = clip_client.get(
        f"/api/videos/{video_id}/clips/{clip_id}",
        headers={"Range": "bytes=0-99"},
    )
    assert response.status_code == 206
    assert len(response.content) <= 100


def test_default_clip_target_duration_is_sixty_seconds() -> None:
    get_settings.cache_clear()
    assert Settings().clip_target_duration_seconds == 60.0


@pytest.mark.ffmpeg
@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg/ffprobe not installed")
def test_clip_metadata_duration_matches_ffprobe_output(clip_client, tmp_path) -> None:
    video_id = uuid.uuid4()
    directory = tmp_path / "jobs" / str(video_id)
    directory.mkdir(parents=True)
    _make_test_mp4(directory / "source.mp4", duration=2.5)

    created = clip_client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "generate_clips"},
    )
    final = _poll_job(clip_client, created.json()["job_id"])
    assert final["status"] == "completed"

    settings = get_settings()
    manifest = read_clips_manifest(settings, video_id)
    for clip in manifest.clips:
        clip_path = clips_directory(settings, video_id) / f"{clip.clip_id}.mp4"
        probe = run_ffprobe(clip_path, settings)
        assert abs(clip.duration - probe.duration_seconds) < 0.25
        assert abs(clip.end_time - clip.start_time - clip.duration) < 0.001


@pytest.mark.ffmpeg
@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg/ffprobe not installed")
def test_failed_regeneration_preserves_existing_clips(clip_client, tmp_path) -> None:
    video_id = uuid.uuid4()
    directory = tmp_path / "jobs" / str(video_id)
    directory.mkdir(parents=True)
    _make_test_mp4(directory / "source.mp4", duration=2.5)

    first = clip_client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "generate_clips"},
    )
    assert _poll_job(clip_client, first.json()["job_id"])["status"] == "completed"

    settings = get_settings()
    before = read_clips_manifest(settings, video_id)
    before_ids = {str(clip.clip_id) for clip in before.clips}

    assert len(before.clips) >= 1
    real_run = clip_generation.run_ffmpeg
    fail_second_job = {"enabled": False}

    def fail_on_second_run(command, **kwargs):
        if fail_second_job["enabled"]:
            raise MediaProcessingError("Simulated FFmpeg failure.")
        return real_run(command, **kwargs)

    with patch.object(clip_generation, "run_ffmpeg", side_effect=fail_on_second_run):
        fail_second_job["enabled"] = True
        second = clip_client.post(
            "/api/jobs",
            json={"video_id": str(video_id), "operation": "generate_clips"},
        )
        assert _poll_job(clip_client, second.json()["job_id"])["status"] == "failed"

    after = read_clips_manifest(settings, video_id)
    after_ids = {str(clip.clip_id) for clip in after.clips}
    assert after_ids == before_ids
    for clip in after.clips:
        assert (clips_directory(settings, video_id) / f"{clip.clip_id}.mp4").is_file()


@pytest.mark.ffmpeg
@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg/ffprobe not installed")
def test_successful_regeneration_removes_orphan_clip_files(clip_client, tmp_path) -> None:
    video_id = uuid.uuid4()
    directory = tmp_path / "jobs" / str(video_id)
    directory.mkdir(parents=True)
    _make_test_mp4(directory / "source.mp4", duration=2.5)

    first = clip_client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "generate_clips"},
    )
    assert _poll_job(clip_client, first.json()["job_id"])["status"] == "completed"
    settings = get_settings()
    first_ids = {clip.clip_id for clip in read_clips_manifest(settings, video_id).clips}

    second = clip_client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "generate_clips"},
    )
    assert _poll_job(clip_client, second.json()["job_id"])["status"] == "completed"

    manifest = read_clips_manifest(settings, video_id)
    current_ids = {clip.clip_id for clip in manifest.clips}
    on_disk = {path.stem for path in clips_directory(settings, video_id).glob("*.mp4")}
    assert on_disk == {str(clip_id) for clip_id in current_ids}
    assert current_ids != first_ids


@pytest.mark.ffmpeg
@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg/ffprobe not installed")
def test_regeneration_manifest_write_failure_preserves_previous_clips(clip_client, tmp_path) -> None:
    video_id = uuid.uuid4()
    directory = tmp_path / "jobs" / str(video_id)
    directory.mkdir(parents=True)
    _make_test_mp4(directory / "source.mp4", duration=2.5)

    first = clip_client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "generate_clips"},
    )
    assert _poll_job(clip_client, first.json()["job_id"])["status"] == "completed"

    settings = get_settings()
    before = read_clips_manifest(settings, video_id)
    before_ids = {clip.clip_id for clip in before.clips}
    before_paths = {
        path.resolve()
        for path in clips_directory(settings, video_id).glob("*.mp4")
    }

    real_write = clip_storage.write_clips_manifest
    fail_write = {"enabled": False}

    def failing_write(*args, **kwargs):
        if fail_write["enabled"]:
            raise OSError("Simulated manifest write failure.")
        return real_write(*args, **kwargs)

    with patch.object(clip_storage, "write_clips_manifest", side_effect=failing_write):
        fail_write["enabled"] = True
        second = clip_client.post(
            "/api/jobs",
            json={"video_id": str(video_id), "operation": "generate_clips"},
        )
        assert _poll_job(clip_client, second.json()["job_id"])["status"] == "failed"

    after = read_clips_manifest(settings, video_id)
    assert {clip.clip_id for clip in after.clips} == before_ids
    after_paths = {
        path.resolve() for path in clips_directory(settings, video_id).glob("*.mp4")
    }
    assert after_paths == before_paths


@pytest.mark.ffmpeg
@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg/ffprobe not installed")
def test_regeneration_cleanup_failure_keeps_new_manifest(clip_client, tmp_path) -> None:
    video_id = uuid.uuid4()
    directory = tmp_path / "jobs" / str(video_id)
    directory.mkdir(parents=True)
    _make_test_mp4(directory / "source.mp4", duration=2.5)

    first = clip_client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "generate_clips"},
    )
    assert _poll_job(clip_client, first.json()["job_id"])["status"] == "completed"

    settings = get_settings()
    first_ids = {clip.clip_id for clip in read_clips_manifest(settings, video_id).clips}

    real_remove = clip_storage.remove_clips_except
    fail_remove = {"enabled": False}

    def failing_remove(*args, **kwargs):
        if fail_remove["enabled"]:
            raise OSError("Simulated cleanup failure.")
        return real_remove(*args, **kwargs)

    with patch.object(clip_storage, "remove_clips_except", side_effect=failing_remove):
        fail_remove["enabled"] = True
        second = clip_client.post(
            "/api/jobs",
            json={"video_id": str(video_id), "operation": "generate_clips"},
        )
        assert _poll_job(clip_client, second.json()["job_id"])["status"] == "completed"

    manifest = read_clips_manifest(settings, video_id)
    current_ids = {clip.clip_id for clip in manifest.clips}
    assert current_ids != first_ids
    for clip in manifest.clips:
        assert (clips_directory(settings, video_id) / f"{clip.clip_id}.mp4").is_file()


def test_generate_clips_invalid_source_fails(client, data_dir) -> None:
    video_id = uuid.uuid4()
    directory = data_dir / "jobs" / str(video_id)
    directory.mkdir(parents=True)
    (directory / "source.mp4").write_bytes(b"not-a-video")

    created = client.post(
        "/api/jobs",
        json={"video_id": str(video_id), "operation": "generate_clips"},
    )
    assert created.status_code == 202
    final = _poll_job(client, created.json()["job_id"], timeout_seconds=15.0)
    assert final["status"] == "failed"

