import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark_ffmpeg = pytest.mark.ffmpeg


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_test_mp4(path: Path) -> None:
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
        "0.4",
        "-pix_fmt",
        "yuv420p",
        "-y",
        str(path),
    ]
    subprocess.run(command, check=True, timeout=30)


@pytest.mark.ffmpeg
@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg/ffprobe not installed")
def test_upload_valid_video(client, data_dir) -> None:
    video_path = data_dir / "sample.mp4"
    _make_test_mp4(video_path)

    with video_path.open("rb") as handle:
        response = client.post(
            "/api/videos/upload",
            files={"file": ("sample.mp4", handle, "video/mp4")},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == "sample.mp4"
    assert body["width"] == 640
    assert body["height"] == 360
    assert body["duration_seconds"] > 0
    assert (data_dir / "jobs" / body["video_id"] / "source.mp4").is_file()


def test_upload_rejects_invalid_video_bytes(client) -> None:
    response = client.post(
        "/api/videos/upload",
        files={"file": ("fake.mp4", b"not a real video", "video/mp4")},
    )

    assert response.status_code == 415
    assert "message" in response.json()


def test_upload_rejects_unsupported_extension(client) -> None:
    response = client.post(
        "/api/videos/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert "supported" in response.json()["message"].lower()


def test_upload_enforces_max_size(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "32")
    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    from fastapi.testclient import TestClient

    payload = b"x" * 64
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/videos/upload",
            files={"file": ("large.mp4", payload, "video/mp4")},
        )

    get_settings.cache_clear()

    assert response.status_code == 413
    assert "too large" in response.json()["message"].lower()
    jobs_dir = tmp_path / "jobs"
    assert not jobs_dir.exists() or not any(jobs_dir.iterdir())
