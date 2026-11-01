import uuid
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.errors import InvalidInputError
from app.core.paths import assert_relative_to, resolve_data_dir
from app.services.video_storage import find_source_video_path


def _seed_video(data_dir: Path, payload: bytes = b"x" * 512) -> uuid.UUID:
    video_id = uuid.uuid4()
    directory = data_dir / "jobs" / str(video_id)
    directory.mkdir(parents=True)
    (directory / "source.mp4").write_bytes(payload)
    return video_id


def test_stream_source_video_full_file(client, data_dir) -> None:
    payload = b"test-video-bytes-" + b"z" * 200
    video_id = _seed_video(data_dir, payload)
    response = client.get(f"/api/videos/{video_id}/source")
    assert response.status_code == 200
    assert response.content == payload
    assert "video/" in response.headers.get("content-type", "")


def test_stream_source_video_range_request(client, data_dir) -> None:
    payload = b"a" * 1000
    video_id = _seed_video(data_dir, payload)
    response = client.get(
        f"/api/videos/{video_id}/source",
        headers={"Range": "bytes=0-99"},
    )
    assert response.status_code == 206
    assert response.content == payload[0:100]
    assert response.headers.get("accept-ranges") == "bytes"


def test_stream_unknown_video_returns_404(client) -> None:
    response = client.get(f"/api/videos/{uuid.uuid4()}/source")
    assert response.status_code == 404


def test_find_source_video_rejects_path_outside_data_dir(data_dir, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    settings = get_settings()
    root = resolve_data_dir(settings.data_dir)

    video_id = uuid.uuid4()
    directory = data_dir / "jobs" / str(video_id)
    directory.mkdir(parents=True)
    outside = data_dir.parent / f"outside-{uuid.uuid4()}.mp4"
    outside.write_bytes(b"bad")

    try:
        directory.joinpath("source.mp4").symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported in this environment")

    with pytest.raises(InvalidInputError):
        find_source_video_path(settings, video_id)
