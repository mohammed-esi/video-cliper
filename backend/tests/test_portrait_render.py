"""Portrait FFmpeg render: sendcmd generation, command safety, and integration."""

import subprocess
from pathlib import Path

import numpy as np
import pytest

from app.core.config import Settings
from app.core.errors import InvalidInputError
from app.schemas.tracking import CropGeometry, CropKeyframe, CropShot, FaceBox
from app.services.ffmpeg_runner import ffmpeg_input_argument
from app.services.ffprobe import run_ffprobe
from app.services.portrait_render import (
    PORTRAIT_HEIGHT,
    PORTRAIT_WIDTH,
    build_portrait_ffmpeg_command,
    build_portrait_filter_graph,
    build_sendcmd_content,
    portrait_output_size,
    render_portrait_clip,
    sample_crop_events_for_sendcmd,
)
from app.services.tracking import source_analysis
from app.services.tracking.crop_path import crop_x_at
from tests.media_helpers import make_moving_box_video, requires_ffmpeg

pytestmark = requires_ffmpeg

MODEL_STAND_IN = b"model-bytes-a"


class BoxDetector:
    def __init__(self, model_path, *, frame_width, frame_height, source_width, source_height, **_):
        self._scale_x = source_width / frame_width
        self._scale_y = source_height / frame_height

    def detect(self, frame_bgr: np.ndarray) -> list[FaceBox]:
        ys, xs = np.nonzero(frame_bgr.max(axis=2) > 200)
        if xs.size == 0:
            return []
        left, right = xs.min(), xs.max() + 1
        top, bottom = ys.min(), ys.max() + 1
        return [
            FaceBox(
                x=left * self._scale_x,
                y=top * self._scale_y,
                width=(right - left) * self._scale_x,
                height=(bottom - top) * self._scale_y,
                confidence=0.95,
            )
        ]


def _geometry() -> CropGeometry:
    from app.schemas.tracking import ActivePicture

    active = ActivePicture(x=0, y=0, width=1280, height=720, reason="no_borders")
    return CropGeometry(
        active_picture=active,
        crop_width=404,
        crop_height=720,
        crop_y=0,
        min_x=0,
        max_x=876,
    )


def test_portrait_output_size_is_1080_by_1920() -> None:
    assert portrait_output_size() == (1080, 1920)


def test_sendcmd_starts_with_full_crop_and_updates_x_only() -> None:
    content = build_sendcmd_content([(0.0, 100), (1.5, 260), (3.0, 400)], _geometry())
    lines = [line.strip() for line in content.strip().splitlines()]
    assert lines[0] == "0.000000 crop w 404, crop h 720, crop x 100, crop y 0;"
    assert lines[1] == "1.500000 crop x 260;"
    assert lines[2] == "3.000000 crop x 400;"


def _zoh_lookup(events: list[tuple[float, int]], local_time: float) -> int:
    keys = [time for time, _ in events]
    position = max(i for i, time in enumerate(keys) if time <= local_time + 1e-9)
    return events[position][1]


def test_sampled_events_track_linear_crop_path_between_keyframes() -> None:
    shots = [
        CropShot(
            start_time=0.0,
            end_time=2.0,
            has_subject=True,
            keyframes=[
                CropKeyframe(time=0.0, x=100),
                CropKeyframe(time=1.0, x=300),
                CropKeyframe(time=2.0, x=500),
            ],
        )
    ]
    geometry = _geometry()
    events = sample_crop_events_for_sendcmd(
        shots, geometry, 0.0, 2.0, sample_fps=10.0
    )
    for local, x in events:
        assert x == crop_x_at(shots, geometry, local)
    # Zero-order hold between commands: at most ~half a frame of lag vs the linear path.
    for step in range(21):
        local = step / 10.0
        expected = crop_x_at(shots, geometry, local)
        assert abs(_zoh_lookup(events, local) - expected) <= 12


def test_sampled_events_do_not_smooth_across_scene_cuts() -> None:
    geometry = _geometry()
    shots = [
        CropShot(
            start_time=0.0,
            end_time=2.0,
            has_subject=True,
            keyframes=[
                CropKeyframe(time=0.0, x=100),
                CropKeyframe(time=1.0, x=100),
                CropKeyframe(time=2.0, x=100),
            ],
        ),
        CropShot(
            start_time=2.0,
            end_time=4.0,
            has_subject=True,
            keyframes=[
                CropKeyframe(time=2.0, x=800),
                CropKeyframe(time=3.0, x=800),
                CropKeyframe(time=4.0, x=800),
            ],
        ),
    ]
    events = sample_crop_events_for_sendcmd(
        shots, geometry, 0.0, 4.0, sample_fps=10.0
    )
    assert _zoh_lookup(events, 1.9) == 100
    assert crop_x_at(shots, geometry, 2.0) == 800
    assert _zoh_lookup(events, 2.0) == 800
    assert all(geometry.min_x <= x <= geometry.max_x and x % 2 == 0 for _, x in events)


def test_sampled_events_skip_unchanged_positions() -> None:
    shots = [
        CropShot(
            start_time=0.0,
            end_time=1.0,
            has_subject=True,
            keyframes=[
                CropKeyframe(time=0.0, x=400),
                CropKeyframe(time=1.0, x=400),
            ],
        )
    ]
    events = sample_crop_events_for_sendcmd(
        shots, _geometry(), 0.0, 1.0, sample_fps=25.0
    )
    assert events == [(0.0, 400), (1.0, 400)]


def test_portrait_filter_graph_uses_sendcmd_crop_and_scale(tmp_path) -> None:
    cmd_file = tmp_path / "crop.txt"
    cmd_file.write_text("0 crop w 10, crop h 10, crop x 0, crop y 0;", encoding="utf-8")
    graph = build_portrait_filter_graph(cmd_file)
    assert "sendcmd=f=" in graph
    assert "crop," in graph
    assert f"scale={PORTRAIT_WIDTH}:{PORTRAIT_HEIGHT}" in graph
    assert "setdar=9/16" in graph


def test_portrait_ffmpeg_command_is_safe_and_seeks_before_input(tmp_path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"not-a-video")
    sendcmd = tmp_path / "cmd.txt"
    sendcmd.write_text("0 crop w 10, crop h 10, crop x 0, crop y 0;", encoding="utf-8")
    command = build_portrait_ffmpeg_command(
        Settings(),
        source_path=source,
        output_path=tmp_path / "out.mp4",
        sendcmd_path=sendcmd,
        start_time=12.345,
        duration=3.0,
        has_audio=True,
    )
    joined = " ".join(command)
    assert "-protocol_whitelist file,pipe" in joined
    assert ffmpeg_input_argument(source) in command
    assert command[command.index("-ss") + 1] == "12.345000"
    assert command[command.index("-t") + 1] == "3.000000"
    assert "-map" in command and "[outv]" in command
    assert "-c:v" in command and "libx264" in command
    assert "-c:a" in command and "aac" in command
    assert "-movflags" in command and "+faststart" in command
    assert str(tmp_path / "out.mp4") in command


@pytest.fixture
def box_analysis_setup(monkeypatch, tmp_path):
    monkeypatch.setattr(source_analysis, "YuNetFaceDetector", BoxDetector)
    model_path = tmp_path / "model.onnx"
    model_path.write_bytes(MODEL_STAND_IN)
    return model_path


def test_render_portrait_clip_produces_1080x1920_with_audio_and_duration(
    tmp_path, box_analysis_setup
) -> None:
    source = tmp_path / "moving.mp4"
    make_moving_box_video(
        source,
        size=(1280, 720),
        duration=2.8,
        box=80,
        start_x=100.0,
        speed_px_per_second=200.0,
        video_delay=0.12,
    )
    output = tmp_path / "portrait.mp4"
    _ = box_analysis_setup
    result = render_portrait_clip(
        Settings(),
        source,
        tmp_path / "analysis",
        start_time=0.4,
        end_time=2.0,
        output_path=output,
    )
    assert output.is_file()
    probe = run_ffprobe(output, Settings())
    assert (probe.width, probe.height) == (1080, 1920)
    assert probe.has_audio
    assert probe.duration_seconds == pytest.approx(1.6, abs=0.15)
    assert result.detection_cache_reused is False


def test_second_render_reuses_detection_cache_without_decoding(
    tmp_path, box_analysis_setup, monkeypatch
) -> None:
    source = tmp_path / "moving.mp4"
    make_moving_box_video(source, duration=2.0, box=80, start_x=50.0)
    output = tmp_path / "portrait.mp4"

    _ = box_analysis_setup
    render_portrait_clip(
        Settings(),
        source,
        tmp_path / "analysis",
        start_time=0.0,
        end_time=1.5,
        output_path=output,
    )

    def boom(*_args, **_kwargs):
        raise AssertionError("detection must not run again")

    monkeypatch.setattr(source_analysis, "iter_sampled_frames", boom)
    second = render_portrait_clip(
        Settings(),
        source,
        tmp_path / "analysis",
        start_time=0.2,
        end_time=1.2,
        output_path=tmp_path / "portrait2.mp4",
    )
    assert second.detection_cache_reused is True


def test_render_uses_atomic_output_and_removes_sendcmd(tmp_path, box_analysis_setup) -> None:
    source = tmp_path / "moving.mp4"
    make_moving_box_video(source, duration=1.5, box=60)
    output = tmp_path / "clip.mp4"
    _ = box_analysis_setup
    render_portrait_clip(
        Settings(),
        source,
        tmp_path / "analysis",
        start_time=0.0,
        end_time=1.0,
        output_path=output,
    )
    assert output.is_file()
    assert not (tmp_path / ".clip.sendcmd.txt").exists()
    assert not (tmp_path / "clip.tmp.mp4").exists()


def test_invalid_range_is_rejected(tmp_path, box_analysis_setup) -> None:
    source = tmp_path / "moving.mp4"
    make_moving_box_video(source, duration=1.0, box=40)
    with pytest.raises(InvalidInputError):
        _ = box_analysis_setup
        render_portrait_clip(
            Settings(),
            source,
            tmp_path / "analysis",
            start_time=0.5,
            end_time=0.5,
            output_path=tmp_path / "out.mp4",
        )


def _video_codec(path: Path) -> str:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_sampled_crop_keeps_moving_subject_visible(tmp_path, box_analysis_setup) -> None:
    from app.services.tracking.source_analysis import analyze_source, crop_path_for_range

    source = tmp_path / "moving.mp4"
    make_moving_box_video(
        source, size=(1280, 720), duration=2.0, box=80, start_x=80.0, speed_px_per_second=180.0
    )
    _ = box_analysis_setup
    analysis = analyze_source(Settings(), source, tmp_path / "analysis")
    shots = crop_path_for_range(analysis, 0.2, 1.8)
    geometry = analysis.crop_path.geometry
    events = sample_crop_events_for_sendcmd(
        shots, geometry, 0.2, 1.8, sample_fps=25.0
    )
    event_times = {local: x for local, x in events}
    for sample in analysis.tracking.subject:
        if sample.time < 0.2 or sample.time > 1.8 or sample.box is None:
            continue
        local = round(sample.time - 0.2, 6)
        keys = [time for time in event_times if time <= local + 1e-9]
        x = event_times[max(keys)]
        box = sample.box
        assert x <= box.x
        assert box.x + box.width <= x + geometry.crop_width


def test_rendered_output_is_h264(tmp_path, box_analysis_setup) -> None:
    source = tmp_path / "moving.mp4"
    make_moving_box_video(source, duration=1.2, box=50)
    output = tmp_path / "out.mp4"
    _ = box_analysis_setup
    render_portrait_clip(
        Settings(),
        source,
        tmp_path / "analysis",
        start_time=0.0,
        end_time=1.0,
        output_path=output,
    )
    assert _video_codec(output) == "h264"
