"""Portrait render infrastructure: cache keys, jobs, stale protection, concurrency."""

import threading
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import Settings, get_settings
from app.core.errors import InvalidInputError
from app.schemas.clip import ClipMetadata
from app.schemas.job import CreateJobRequest, JobOperation, JobStatus
from app.schemas.portrait import PortraitRenderRecord
from app.services import job_manager
from app.services.clip_storage import write_clips_manifest
from app.services.clip_trim import update_clip_trim
from app.services.portrait_clip_render import (
    build_portrait_render_plan,
    clear_portrait_inflight_for_tests,
    enqueue_portrait_render,
)
from app.services.portrait_storage import (
    build_render_key_for_clip,
    commit_portrait_render,
    find_portrait_record,
    portrait_file_path,
    read_portraits_manifest,
)
from tests.media_helpers import make_moving_box_video, requires_ffmpeg


@pytest.fixture(autouse=True)
def _clear_inflight() -> None:
    clear_portrait_inflight_for_tests()
    yield
    clear_portrait_inflight_for_tests()


@pytest.fixture
def settings(tmp_path, monkeypatch) -> Settings:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


def _seed_clip_job(
    settings: Settings,
    *,
    duration: float = 3.0,
    start: float = 0.5,
    end: float = 2.0,
) -> tuple[uuid.UUID, uuid.UUID, Path]:
    video_id = uuid.uuid4()
    clip_id = uuid.uuid4()
    job_dir = Path(settings.data_dir) / "jobs" / str(video_id)
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
    return video_id, clip_id, source


def _fake_render(_settings, _source_path, _analysis_dir, *, start_time, end_time, output_path):
    duration = max(0.4, end_time - start_time)
    make_moving_box_video(
        output_path,
        size=(640, 360),
        duration=min(duration, 1.0),
        box=40,
    )


@pytest.mark.ffmpeg
@requires_ffmpeg
@pytest.mark.ffmpeg
@requires_ffmpeg
def test_render_key_changes_when_cached_analysis_artifacts_change(
    settings, monkeypatch, tmp_path
) -> None:
    from app.services.tracking import source_analysis
    from app.services.tracking.analysis_cache import CROP_PATH_FILE
    from app.services.portrait_storage import analysis_directory
    from tests.test_tracking_pipeline import MODEL_STAND_IN, BoxDetector, analyze

    monkeypatch.setattr(source_analysis, "YuNetFaceDetector", BoxDetector)
    model_path = tmp_path / "model.onnx"
    model_path.write_bytes(MODEL_STAND_IN)
    video_id, clip_id, source = _seed_clip_job(settings)
    job_dir = Path(settings.data_dir) / "jobs" / str(video_id)
    analyze(source, job_dir, model_path)
    first = build_render_key_for_clip(
        settings, video_id, clip_id, start_time=0.5, end_time=2.0, source_path=source
    )
    crop_file = analysis_directory(settings, video_id) / CROP_PATH_FILE
    crop_file.write_bytes(crop_file.read_bytes() + b" ")
    second = build_render_key_for_clip(
        settings, video_id, clip_id, start_time=0.5, end_time=2.0, source_path=source
    )
    assert first != second


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_render_plan_uses_persisted_trim_not_generated_bounds(settings) -> None:
    video_id, clip_id, _ = _seed_clip_job(settings, start=0.4, end=1.6)
    plan = build_portrait_render_plan(settings, video_id, clip_id)
    assert plan.start_time == 0.4
    assert plan.end_time == 1.6


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_render_key_changes_when_trim_changes(settings) -> None:
    video_id, clip_id, source = _seed_clip_job(settings, start=0.5, end=2.0)
    from app.schemas.clip import ClipTrimUpdate

    first = build_render_key_for_clip(
        settings, video_id, clip_id, start_time=0.5, end_time=2.0, source_path=source
    )
    update_clip_trim(
        settings, video_id, clip_id, ClipTrimUpdate(start_time=0.8, end_time=2.2)
    )
    second = build_render_key_for_clip(
        settings, video_id, clip_id, start_time=0.8, end_time=2.2, source_path=source
    )
    assert first != second


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_cache_reuse_skips_second_render(settings) -> None:
    video_id, clip_id, source = _seed_clip_job(settings)
    render_key = build_render_key_for_clip(
        settings, video_id, clip_id, start_time=0.5, end_time=2.0, source_path=source
    )
    path = portrait_file_path(settings, video_id, render_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00" * 128)
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
    job_manager.initialize(settings)
    with patch(
        "app.services.portrait_clip_render.render_portrait_clip",
        side_effect=AssertionError("should not render"),
    ):
        response = enqueue_portrait_render(settings, video_id, clip_id)
    assert response.status == JobStatus.COMPLETED
    assert response.result["cached"] is True


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_stale_render_does_not_replace_current_portrait(settings) -> None:
    video_id, clip_id, source = _seed_clip_job(settings, start=0.5, end=2.0)
    from app.schemas.clip import ClipTrimUpdate

    original_key = build_render_key_for_clip(
        settings, video_id, clip_id, start_time=0.5, end_time=2.0, source_path=source
    )
    current_path = portrait_file_path(settings, video_id, original_key)
    current_path.parent.mkdir(parents=True, exist_ok=True)
    current_path.write_bytes(b"CURRENT")
    commit_portrait_render(
        settings,
        video_id,
        PortraitRenderRecord(
            clip_id=clip_id,
            render_key=original_key,
            start_time=0.5,
            end_time=2.0,
            storage_name=current_path.name,
            width=1080,
            height=1920,
            has_audio=False,
        ),
    )

    trim_applied = threading.Event()

    def slow_render(*_args, **kwargs):
        if not trim_applied.wait(timeout=2.0):
            raise AssertionError("trim did not complete before render finished")
        output_path = kwargs["output_path"]
        output_path.write_bytes(b"STALE_ATTEMPT")

    job_manager.initialize(settings)
    with patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=slow_render):
        request = CreateJobRequest(
            video_id=video_id,
            operation=JobOperation.RENDER_PORTRAIT_CLIP,
            clip_id=clip_id,
            render_key=original_key,
        )
        created = job_manager.create_job(request)

        def trim_during_render() -> None:
            time.sleep(0.05)
            update_clip_trim(
                settings, video_id, clip_id, ClipTrimUpdate(start_time=1.0, end_time=2.5)
            )
            trim_applied.set()

        trim_thread = threading.Thread(target=trim_during_render)
        trim_thread.start()
        job_manager.run_job(created.job_id)
        trim_thread.join(timeout=3.0)

    manifest = read_portraits_manifest(settings, video_id)
    assert len(manifest.renders) == 1
    assert manifest.renders[0].render_key == original_key
    assert current_path.read_bytes() == b"CURRENT"
    final = job_manager.get_job(created.job_id)
    assert final.result["stale_discarded"] is True


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_concurrent_enqueue_same_render_key_returns_same_job(settings) -> None:
    video_id, clip_id, _ = _seed_clip_job(settings)
    job_manager.initialize(settings)
    with patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=_fake_render):
        first = enqueue_portrait_render(settings, video_id, clip_id)
        second = enqueue_portrait_render(settings, video_id, clip_id)
    assert first.job_id == second.job_id
    assert first.status == JobStatus.QUEUED


def test_invalid_render_key_rejects_path_traversal(settings) -> None:
    video_id = uuid.uuid4()
    with pytest.raises(InvalidInputError):
        portrait_file_path(settings, video_id, "../evil")


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_render_failure_cleans_work_file(settings) -> None:
    video_id, clip_id, _ = _seed_clip_job(settings)
    job_manager.initialize(settings)
    plan = build_portrait_render_plan(settings, video_id, clip_id)
    work = plan.output_path.with_name(f"{plan.render_key}.work.mp4")

    def boom(*_args, **_kwargs):
        work.parent.mkdir(parents=True, exist_ok=True)
        work.with_name(f"{work.stem}.tmp.mp4").write_bytes(b"partial")
        raise RuntimeError("ffmpeg failed")

    request = CreateJobRequest(
        video_id=video_id,
        operation=JobOperation.RENDER_PORTRAIT_CLIP,
        clip_id=clip_id,
        render_key=plan.render_key,
    )
    created = job_manager.create_job(request)
    with patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=boom):
        job_manager.run_job(created.job_id)
    assert not work.exists()
    assert not work.with_name(f"{work.stem}.tmp.mp4").exists()
    assert find_portrait_record(settings, video_id, clip_id, plan.render_key) is None


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_portrait_job_completes_and_registers_manifest(settings) -> None:
    video_id, clip_id, _ = _seed_clip_job(settings)
    job_manager.initialize(settings)
    with patch("app.services.portrait_clip_render.render_portrait_clip", side_effect=_fake_render):
        response = enqueue_portrait_render(settings, video_id, clip_id)
        if response.status == JobStatus.QUEUED:
            job_manager.run_job(response.job_id)
            response = job_manager.get_job(response.job_id)
    assert response.status == JobStatus.COMPLETED
    record = read_portraits_manifest(settings, video_id).renders[0]
    assert record.clip_id == clip_id
    assert portrait_file_path(settings, video_id, record.render_key).is_file()
