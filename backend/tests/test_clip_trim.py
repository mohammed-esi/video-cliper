import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import InvalidInputError
from app.main import create_app
from app.schemas.clip import ClipMetadata, ClipTrimUpdate
from app.services.clip_storage import manifest_path, write_clips_manifest
from app.services.clip_trim import update_clip_trim, validate_trim_range


@pytest.fixture
def trim_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def _write_manifest(
    settings,
    video_id: uuid.UUID,
    clips: list[ClipMetadata],
    *,
    job_dir: Path,
) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "clips").mkdir(exist_ok=True)
    for clip in clips:
        (job_dir / "clips" / f"{clip.clip_id}.mp4").write_bytes(b"\x00")
    (job_dir / "source.mp4").write_bytes(b"\x00")
    write_clips_manifest(settings, video_id, clips)


def test_validate_trim_range_shortens_and_extends() -> None:
    start, end = validate_trim_range(
        start_time=45.0,
        end_time=115.0,
        source_duration=200.0,
    )
    assert start == 45.0
    assert end == 115.0


def test_validate_trim_range_rejects_past_source_end() -> None:
    with pytest.raises(InvalidInputError, match="past the end"):
        validate_trim_range(
            start_time=0.0,
            end_time=201.0,
            source_duration=200.0,
        )


def test_validate_trim_range_requires_minimum_duration() -> None:
    with pytest.raises(InvalidInputError, match="at least"):
        validate_trim_range(
            start_time=1.0,
            end_time=1.05,
            source_duration=10.0,
        )


def test_patch_clip_trim_persists(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    settings = get_settings()

    video_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    job_dir = tmp_path / "jobs" / str(video_id)
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
    _write_manifest(settings, video_id, [clip], job_dir=job_dir)

    from unittest.mock import patch

    with patch(
        "app.services.clip_trim.run_ffprobe",
        return_value=type(
            "Probe",
            (),
            {"duration_seconds": 300.0},
        )(),
    ):
        updated = update_clip_trim(
            settings,
            video_id,
            clip_id,
            ClipTrimUpdate(start_time=45.0, end_time=115.0),
        )

    assert updated.start_time == 45.0
    assert updated.end_time == 115.0
    assert updated.generated_start_time == 60.0
    assert updated.generated_end_time == 120.0

    stored = json.loads(manifest_path(settings, video_id).read_text(encoding="utf-8"))
    assert stored["clips"][0]["start_time"] == 45.0


def test_list_clips_includes_source_duration(trim_client, tmp_path, monkeypatch) -> None:
    settings = get_settings()
    video_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    job_dir = tmp_path / "jobs" / str(video_id)
    clip = ClipMetadata(
        clip_id=clip_id,
        video_id=video_id,
        start_time=0.0,
        end_time=10.0,
        duration=10.0,
        generated_start_time=0.0,
        generated_end_time=10.0,
        storage_name=f"clips/{clip_id}.mp4",
        width=640,
        height=360,
        has_audio=False,
    )
    _write_manifest(settings, video_id, [clip], job_dir=job_dir)

    from unittest.mock import patch

    with patch(
        "app.services.clip_trim.run_ffprobe",
        return_value=type(
            "Probe",
            (),
            {"duration_seconds": 120.5},
        )(),
    ):
        response = trim_client.get(f"/api/videos/{video_id}/clips")

    assert response.status_code == 200
    body = response.json()
    assert body["source_duration_seconds"] == 120.5
    assert body["clips"][0]["generated_start_time"] == 0.0
