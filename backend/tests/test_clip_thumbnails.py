import json
import shutil
import subprocess
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import MediaProcessingError, NotFoundError
from app.main import create_app
from app.schemas.clip import ClipMetadata
from app.services.clip_storage import write_clips_manifest
from app.services.clip_thumbnails import (
    get_or_create_clip_thumbnail_path,
    invalidate_clip_thumbnail,
    thumbnail_midpoint,
)
from app.services.clip_trim import update_clip_trim
from app.schemas.clip import ClipTrimUpdate


@pytest.fixture
def thumb_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def _seed_clip_job(tmp_path: Path, video_id: uuid.UUID, clip_id: uuid.UUID) -> Path:
    job_dir = tmp_path / "jobs" / str(video_id)
    (job_dir / "clips").mkdir(parents=True)
    (job_dir / "source.mp4").write_bytes(b"\x00")
    (job_dir / "clips" / f"{clip_id}.mp4").write_bytes(b"\x00")
    clip = ClipMetadata(
        clip_id=clip_id,
        video_id=video_id,
        start_time=60.0,
        end_time=120.0,
        duration=60.0,
        generated_start_time=60.0,
        generated_end_time=120.0,
        storage_name=f"clips/{clip_id}.mp4",
        width=640,
        height=360,
        has_audio=True,
    )
    write_clips_manifest(get_settings(), video_id, [clip])
    return job_dir


def test_thumbnail_midpoint_uses_edited_range_center() -> None:
    assert thumbnail_midpoint(45.0, 115.0) == 80.0


def test_get_or_create_generates_and_caches(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()
    video_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    _seed_clip_job(tmp_path, video_id, clip_id)

    calls: list[float] = []

    def _fake_generate(settings, *, source_path, output_path, timestamp):
        calls.append(timestamp)
        output_path.write_bytes(b"fake-jpeg")

    with patch(
        "app.services.clip_thumbnails._generate_thumbnail_file",
        side_effect=_fake_generate,
    ):
        first = get_or_create_clip_thumbnail_path(settings, video_id, clip_id)
        second = get_or_create_clip_thumbnail_path(settings, video_id, clip_id)

    assert first == second
    assert calls == [90.0]


def test_trim_invalidates_cached_thumbnail(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()
    video_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    _seed_clip_job(tmp_path, video_id, clip_id)

    with patch(
        "app.services.clip_thumbnails._generate_thumbnail_file",
        side_effect=lambda *_args, **kwargs: kwargs["output_path"].write_bytes(
            b"jpeg"
        ),
    ):
        get_or_create_clip_thumbnail_path(settings, video_id, clip_id)

    with patch(
        "app.services.clip_trim.run_ffprobe",
        return_value=type("Probe", (), {"duration_seconds": 300.0})(),
    ):
        update_clip_trim(
            settings,
            video_id,
            clip_id,
            ClipTrimUpdate(start_time=50.0, end_time=110.0),
        )

    meta_path = tmp_path / "jobs" / str(video_id) / "thumbnails" / f"{clip_id}.json"
    assert not meta_path.is_file()


def test_missing_clip_returns_not_found(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()
    video_id = uuid.uuid4()
    with pytest.raises(NotFoundError):
        get_or_create_clip_thumbnail_path(settings, video_id, uuid.uuid4())


def test_ffmpeg_failure_surfaces_media_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()
    video_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    _seed_clip_job(tmp_path, video_id, clip_id)

    with patch(
        "app.services.clip_thumbnails._generate_thumbnail_file",
        side_effect=MediaProcessingError("ffmpeg failed"),
    ):
        with pytest.raises(MediaProcessingError):
            get_or_create_clip_thumbnail_path(settings, video_id, clip_id)


def test_thumbnail_endpoint_returns_image(thumb_client, tmp_path, monkeypatch) -> None:
    settings = get_settings()
    video_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    _seed_clip_job(tmp_path, video_id, clip_id)

    with patch(
        "app.services.clip_thumbnails._generate_thumbnail_file",
        side_effect=lambda *_args, **kwargs: kwargs["output_path"].write_bytes(
            b"jpeg"
        ),
    ):
        response = thumb_client.get(
            f"/api/videos/{video_id}/clips/{clip_id}/thumbnail",
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")


def test_generate_thumbnail_waits_for_ffmpeg_lock(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()
    video_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    _seed_clip_job(tmp_path, video_id, clip_id)

    calls = {"count": 0}

    def _busy_then_ok(command, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise MediaProcessingError(
                "Another FFmpeg process is already running."
            )
        Path(command[-1]).write_bytes(b"jpeg")

    with patch(
        "app.services.clip_thumbnails.run_ffmpeg",
        side_effect=_busy_then_ok,
    ):
        path = get_or_create_clip_thumbnail_path(settings, video_id, clip_id)

    assert path.is_file()
    assert calls["count"] >= 2


def test_invalidate_clip_thumbnail_removes_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()
    video_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    job_dir = _seed_clip_job(tmp_path, video_id, clip_id)
    thumb_dir = job_dir / "thumbnails"
    thumb_dir.mkdir(exist_ok=True)
    image = thumb_dir / f"{clip_id}.jpg"
    meta = thumb_dir / f"{clip_id}.json"
    image.write_bytes(b"x")
    meta.write_text(json.dumps({"start_time": 1, "end_time": 2}), encoding="utf-8")

    invalidate_clip_thumbnail(settings, video_id, clip_id)
    assert not image.is_file()
    assert not meta.is_file()


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_test_mp4(path: Path, duration: float = 2.0) -> None:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=640x360:rate=30",
        "-t",
        str(duration),
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        "-y",
        str(path),
    ]
    subprocess.run(command, check=True, timeout=60)


@pytest.mark.ffmpeg
@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not installed")
def test_thumbnail_http_endpoint_generates_real_jpeg(
    thumb_client,
    tmp_path,
    monkeypatch,
) -> None:
    video_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    job_dir = _seed_clip_job(tmp_path, video_id, clip_id)
    source = job_dir / "source.mp4"
    _make_test_mp4(source, duration=3.0)
    # Default seed uses 60–120s; short lavfi source is only 3s.
    write_clips_manifest(
        get_settings(),
        video_id,
        [
            ClipMetadata(
                clip_id=clip_id,
                video_id=video_id,
                start_time=0.5,
                end_time=2.5,
                duration=2.0,
                generated_start_time=0.5,
                generated_end_time=2.5,
                storage_name=f"clips/{clip_id}.mp4",
                width=640,
                height=360,
                has_audio=False,
            )
        ],
    )

    url = f"/api/videos/{video_id}/clips/{clip_id}/thumbnail"
    first = thumb_client.get(url)
    assert first.status_code == 200
    assert first.headers["content-type"].startswith("image/jpeg")
    assert first.content[:2] == b"\xff\xd8"
    assert len(first.content) > 100

    thumb_path = tmp_path / "jobs" / str(video_id) / "thumbnails" / f"{clip_id}.jpg"
    assert thumb_path.is_file()
    assert thumb_path.stat().st_size > 0

    second = thumb_client.get(url)
    assert second.status_code == 200
    assert second.content == first.content
