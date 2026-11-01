import threading

import numpy as np
import pytest

from app.core.config import Settings
from app.core.errors import MediaProcessingError
from app.schemas.tracking import SceneCut
from app.services.tracking.face_detector import (
    DEFAULT_MODEL_PATH,
    YuNetFaceDetector,
    parse_yunet_output,
)
from app.services.tracking.frame_sampling import build_sampling_command, iter_sampled_frames
from app.services.tracking.scene_cuts import (
    build_scene_command,
    detect_scene_cuts,
    filter_scene_cuts,
    parse_scene_metadata,
)
from tests.media_helpers import (
    make_hard_cut_video,
    make_moving_box_video,
    requires_ffmpeg,
)


def _row(x, y, w, h, score) -> list[float]:
    # YuNet rows: box, five landmark (x, y) pairs, score.
    return [x, y, w, h, *([0.0] * 10), score]


# --- YuNet output parsing -------------------------------------------------


def test_parse_maps_analysis_pixels_to_source_pixels() -> None:
    raw = np.array([_row(100, 50, 40, 60, 0.93)], dtype=np.float32)
    faces = parse_yunet_output(raw, scale_x=3.0, scale_y=3.0, source_width=1920, source_height=1080)
    assert len(faces) == 1
    face = faces[0]
    assert (face.x, face.y, face.width, face.height) == (300.0, 150.0, 120.0, 180.0)
    assert face.confidence == pytest.approx(0.93, abs=1e-3)


def test_parse_returns_empty_for_no_detections() -> None:
    kwargs = dict(scale_x=1.0, scale_y=1.0, source_width=640, source_height=360)
    assert parse_yunet_output(None, **kwargs) == []
    assert parse_yunet_output(np.empty((0, 15), dtype=np.float32), **kwargs) == []


def test_parse_supports_multiple_faces() -> None:
    raw = np.array([_row(10, 10, 50, 50, 0.9), _row(300, 40, 60, 60, 0.7)], dtype=np.float32)
    faces = parse_yunet_output(raw, scale_x=1.0, scale_y=1.0, source_width=640, source_height=360)
    assert [round(face.x) for face in faces] == [10, 300]


def test_parse_clips_boxes_to_the_frame_and_drops_degenerate_rows() -> None:
    raw = np.array(
        [
            _row(-20, -10, 60, 60, 0.9),  # hangs off the top-left corner
            _row(620, 340, 60, 60, 0.9),  # hangs off the bottom-right corner
            _row(700, 10, 50, 50, 0.9),  # entirely outside
            _row(10, 10, 0.2, 50, 0.9),  # sliver
            _row(np.nan, 10, 50, 50, 0.9),  # non-finite
        ],
        dtype=np.float32,
    )
    faces = parse_yunet_output(raw, scale_x=1.0, scale_y=1.0, source_width=640, source_height=360)
    assert len(faces) == 2
    first, second = faces
    assert (first.x, first.y) == (0.0, 0.0)
    assert first.width == 40.0 and first.height == 50.0
    assert second.x + second.width == 640.0 and second.y + second.height == 360.0


def test_parse_rejects_unexpected_output_shape() -> None:
    with pytest.raises(ValueError):
        parse_yunet_output(
            np.zeros((2, 6), dtype=np.float32),
            scale_x=1.0,
            scale_y=1.0,
            source_width=640,
            source_height=360,
        )


def test_yunet_model_loads_and_handles_frames_without_faces() -> None:
    detector = YuNetFaceDetector(
        DEFAULT_MODEL_PATH, frame_width=640, frame_height=360, source_width=1280, source_height=720
    )
    assert detector.detect(np.zeros((360, 640, 3), dtype=np.uint8)) == []
    noise = np.random.default_rng(0).integers(0, 255, (360, 640, 3), dtype=np.uint8)
    assert isinstance(detector.detect(noise), list)


def test_yunet_missing_model_is_a_clean_error(tmp_path) -> None:
    with pytest.raises(MediaProcessingError):
        YuNetFaceDetector(
            tmp_path / "missing.onnx",
            frame_width=640,
            frame_height=360,
            source_width=640,
            source_height=360,
        )


# --- Frame sampling --------------------------------------------------------


def test_sampling_command_is_a_safe_argument_list(tmp_path) -> None:
    command = build_sampling_command(
        Settings(), tmp_path / "source.mp4", sample_fps=5.0, frame_width=640, frame_height=360
    )
    assert isinstance(command, list)
    assert "-nostdin" in command
    assert command[command.index("-protocol_whitelist") + 1] == "file,pipe"
    assert command[command.index("-i") + 1].startswith("file:")
    assert (
        "fps=fps=5.000000:start_time=0:round=up,scale=640:360:flags=area" in command
    )


def _content_time_error(frame_image: np.ndarray, stamp: float, speed: float, box: int) -> float:
    """Source time of the picture shown minus the sample's stamp, from the box position."""
    white = np.flatnonzero(frame_image[:, :, 0].max(axis=0) > 200)
    assert white.size > 0, "box should be visible"
    left_edge = white.min()
    return left_edge / speed - stamp


@requires_ffmpeg
@pytest.mark.ffmpeg
@pytest.mark.parametrize("video_delay", [0.0, 0.12])
def test_sampled_frames_show_the_source_at_their_timestamp(tmp_path, video_delay) -> None:
    """A sample must show the latest source frame at or before its stamp (never later)."""
    source = tmp_path / "source.mp4"
    speed, box, source_frame = 200.0, 40, 1 / 25
    # The box leaves the 640 px frame after (640 - box) / speed = 3.0 s.
    make_moving_box_video(
        source,
        size=(640, 360),
        duration=2.8,
        box=box,
        speed_px_per_second=speed,
        video_delay=video_delay,
    )

    frames = list(
        iter_sampled_frames(
            Settings(),
            source,
            sample_fps=5.0,
            frame_width=640,
            frame_height=360,
            timeout_seconds=60.0,
        )
    )
    assert 13 <= len(frames) <= 15
    assert frames[0].image.shape == (360, 640, 3)
    assert [frame.time for frame in frames[:3]] == pytest.approx([0.0, 0.2, 0.4])
    # With a delayed start the box timeline starts `video_delay` into the file.
    for frame in frames:
        if frame.time < video_delay + 0.01:
            continue
        error = _content_time_error(frame.image, frame.time - video_delay, speed, box)
        assert -source_frame - 0.006 <= error <= 0.006


@requires_ffmpeg
@pytest.mark.ffmpeg
def test_sampling_an_unreadable_file_raises_a_clean_error(tmp_path) -> None:
    broken = tmp_path / "source.mp4"
    broken.write_bytes(b"not a video")
    with pytest.raises(MediaProcessingError):
        list(
            iter_sampled_frames(
                Settings(),
                broken,
                sample_fps=5.0,
                frame_width=64,
                frame_height=36,
                timeout_seconds=30.0,
            )
        )


@requires_ffmpeg
@pytest.mark.ffmpeg
def test_sampling_stops_when_cancelled(tmp_path) -> None:
    source = tmp_path / "source.mp4"
    make_moving_box_video(source, size=(640, 360), duration=3.0, box=40)
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(MediaProcessingError):
        list(
            iter_sampled_frames(
                Settings(),
                source,
                sample_fps=5.0,
                frame_width=640,
                frame_height=360,
                timeout_seconds=30.0,
                cancelled=cancelled,
            )
        )


# --- Scene cuts --------------------------------------------------------------

_FFMPEG_METADATA = """\
frame:0    pts:640     pts_time:0.04
lavfi.scene_score=0.771646
frame:1    pts:31360   pts_time:1.96
lavfi.scene_score=0.502234
frame:2    pts:32000   pts_time:2.000
lavfi.scene_score=0.187000
"""


def test_scene_metadata_pairs_times_with_scores() -> None:
    cuts = parse_scene_metadata(_FFMPEG_METADATA)
    assert [(cut.time, cut.score) for cut in cuts] == [(0.04, 0.771646), (1.96, 0.502234), (2.0, 0.187)]


def test_scene_metadata_ignores_noise_and_orphan_lines() -> None:
    text = "lavfi.scene_score=0.9\nrandom log line\nframe:3 pts:1 pts_time:1.5\n"
    assert parse_scene_metadata(text) == []


def test_scene_filter_applies_threshold_and_min_gap_and_ignores_first_frame() -> None:
    cuts = [
        SceneCut(time=0.04, score=0.77),  # first-frame artefact
        SceneCut(time=2.0, score=0.5),
        SceneCut(time=2.3, score=0.8),  # within the gap of the previous: strongest wins
        SceneCut(time=5.0, score=0.2),  # below threshold
        SceneCut(time=9.0, score=0.4),
    ]
    assert filter_scene_cuts(cuts, min_score=0.3, min_gap_seconds=0.5) == [2.3, 9.0]


def test_scene_command_is_a_safe_argument_list(tmp_path) -> None:
    command = build_scene_command(Settings(), tmp_path / "source.mp4")
    assert isinstance(command, list)
    assert "-nostdin" in command
    assert command[command.index("-protocol_whitelist") + 1] == "file,pipe"
    assert command[command.index("-i") + 1].startswith("file:")
    assert any("select='gt(scene," in part for part in command)


@requires_ffmpeg
@pytest.mark.ffmpeg
def test_hard_cut_is_detected_at_the_right_time(tmp_path) -> None:
    source = tmp_path / "source.mp4"
    make_hard_cut_video(source, segment_seconds=2.0)
    cuts = detect_scene_cuts(Settings(), source, timeout_seconds=60.0)
    kept = filter_scene_cuts(cuts, min_score=0.3, min_gap_seconds=0.5)
    assert len(kept) == 1
    assert kept[0] == pytest.approx(2.0, abs=0.1)


@requires_ffmpeg
@pytest.mark.ffmpeg
def test_moving_subject_without_a_cut_produces_no_scene_cut(tmp_path) -> None:
    source = tmp_path / "source.mp4"
    make_moving_box_video(source, size=(640, 360), duration=4.0, box=60, speed_px_per_second=120.0)
    cuts = detect_scene_cuts(Settings(), source, timeout_seconds=60.0)
    assert filter_scene_cuts(cuts, min_score=0.3, min_gap_seconds=0.5) == []
