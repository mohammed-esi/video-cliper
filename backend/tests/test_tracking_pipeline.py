"""End-to-end analysis on real FFmpeg-decoded frames.

Only the face detector is replaced: `BoxDetector` finds the synthetic white square in the
frames FFmpeg really decodes, so sampling, scene detection, caching, tracking and crop
planning all run for real. The real YuNet model is covered by `test_real_video_*`.
"""

import json
import os
import shutil
from pathlib import Path

import numpy as np
import pytest
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import InvalidInputError
from app.schemas.tracking import (
    SCHEMA_VERSION,
    CropParams,
    DetectionCacheFile,
    FaceBox,
    TrackingParams,
)
from app.services.tracking import analysis_cache, source_analysis
from app.services.tracking.analysis_cache import (
    CROP_PATH_FILE,
    DETECTIONS_FILE,
    SCENES_FILE,
    TRACKING_FILE,
    read_artifact,
    write_artifact,
)
from app.services.tracking.crop_path import crop_x_at
from app.services.tracking.source_analysis import analyze_source, crop_path_for_range
from tests.media_helpers import (
    make_bordered_video,
    make_hard_cut_video,
    make_jumping_box_video,
    make_moving_box_video,
    requires_ffmpeg,
)

pytestmark = requires_ffmpeg

MODEL_STAND_IN = b"model-bytes-a"


class BoxDetector:
    """Reports the bounding box of bright pixels as one face (source coordinates)."""

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


class NoFacesDetector:
    def __init__(self, *_args, **_kwargs):
        pass

    def detect(self, frame_bgr: np.ndarray) -> list[FaceBox]:
        return []


class ConstantDetector:
    """Always reports the same face, regardless of content."""

    def __init__(self, model_path, *, source_width, source_height, **_):
        self._box = FaceBox(x=300, y=200, width=90, height=90, confidence=0.9)

    def detect(self, frame_bgr: np.ndarray) -> list[FaceBox]:
        return [self._box]


@pytest.fixture
def model_path(tmp_path: Path) -> Path:
    path = tmp_path / "model.onnx"
    path.write_bytes(MODEL_STAND_IN)
    return path


@pytest.fixture
def use_box_detector(monkeypatch):
    monkeypatch.setattr(source_analysis, "YuNetFaceDetector", BoxDetector)


def analyze(source: Path, tmp_path: Path, model_path: Path, **kwargs):
    return analyze_source(
        Settings(), source, tmp_path / "analysis", model_path=model_path, **kwargs
    )


@pytest.fixture
def moving_source(tmp_path: Path) -> Path:
    path = tmp_path / "moving.mp4"
    make_moving_box_video(path, duration=2.8, box=80, start_x=100.0, speed_px_per_second=200.0)
    return path


def forbid_decoding(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("the source must not be decoded again")

    monkeypatch.setattr(source_analysis, "iter_sampled_frames", boom)
    monkeypatch.setattr(source_analysis.scene_cuts, "detect_scene_cuts", boom)


# --- Tracking and crop on real decoded frames ---------------------------------


def test_crop_follows_a_moving_subject_and_keeps_it_visible(
    moving_source, tmp_path, model_path, use_box_detector
) -> None:
    analysis = analyze(moving_source, tmp_path, model_path)
    geometry = analysis.crop_path.geometry

    assert analysis.tracking.cut_times == []
    assert len(analysis.tracking.tracks) == 1
    assert all(sample.state == "detected" for sample in analysis.tracking.subject)

    xs = []
    for sample in analysis.tracking.subject:
        x = crop_x_at(analysis.crop_path.shots, geometry, sample.time)
        xs.append(x)
        assert x % 2 == 0 and geometry.min_x <= x <= geometry.max_x
        assert sample.box is not None
        assert x <= sample.box.x
        assert sample.box.x + sample.box.width <= x + geometry.crop_width
    assert max(xs) - min(xs) > 150  # the subject travels ~560 px; the crop moved with it
    assert xs[-1] > xs[0]


def test_detection_timestamps_come_from_the_video(
    moving_source, tmp_path, model_path, use_box_detector
) -> None:
    analysis = analyze(moving_source, tmp_path, model_path)
    times = [frame.time for frame in analysis.detections.frames]
    assert times[0] == pytest.approx(0.0, abs=0.01)
    assert np.diff(times) == pytest.approx(0.2, abs=0.01)
    for frame in analysis.detections.frames:
        expected_left = 100.0 + 200.0 * frame.time
        assert frame.faces[0].x == pytest.approx(expected_left, abs=14.0)


def test_a_face_jump_inside_one_shot_is_not_a_scene_cut(
    tmp_path, model_path, use_box_detector
) -> None:
    source = tmp_path / "jump.mp4"
    make_jumping_box_video(source, duration=4.0, jump_time=2.0)
    analysis = analyze(source, tmp_path, model_path)

    assert analysis.tracking.cut_times == []
    assert len(analysis.crop_path.shots) == 1
    geometry = analysis.crop_path.geometry
    before = crop_x_at(analysis.crop_path.shots, geometry, 1.0)
    after = crop_x_at(analysis.crop_path.shots, geometry, 3.5)
    assert after > before + 300  # the camera moved to the new position, it did not cut


def test_hard_cut_splits_tracks_and_crop_shots_even_for_an_identical_face_position(
    tmp_path, model_path, monkeypatch
) -> None:
    monkeypatch.setattr(source_analysis, "YuNetFaceDetector", ConstantDetector)
    source = tmp_path / "cut.mp4"
    make_hard_cut_video(source, segment_seconds=2.0)
    analysis = analyze(source, tmp_path, model_path)

    assert len(analysis.tracking.cut_times) == 1
    assert analysis.tracking.cut_times[0] == pytest.approx(2.0, abs=0.1)
    assert len(analysis.tracking.tracks) == 2
    assert len(analysis.crop_path.shots) == 2
    assert analysis.tracking.tracks[0].shot_index != analysis.tracking.tracks[1].shot_index


def test_video_without_faces_gets_a_centred_crop(tmp_path, model_path, monkeypatch) -> None:
    monkeypatch.setattr(source_analysis, "YuNetFaceDetector", NoFacesDetector)
    source = tmp_path / "plain.mp4"
    make_hard_cut_video(source, size=(1280, 720), segment_seconds=1.0)
    analysis = analyze(source, tmp_path, model_path)
    geometry = analysis.crop_path.geometry

    assert analysis.tracking.tracks == []
    assert not any(shot.has_subject for shot in analysis.crop_path.shots)
    centred = (geometry.min_x + geometry.max_x) // 2
    for shot in analysis.crop_path.shots:
        assert all(abs(keyframe.x - centred) <= 2 for keyframe in shot.keyframes)


# --- Active picture on real decoded frames ----------------------------------


@pytest.mark.parametrize(
    ("inner", "outer", "offset", "picture"),
    [
        pytest.param((480, 360), (640, 360), (80, 0), (80, 0, 480, 360), id="pillarbox"),
        pytest.param((640, 268), (640, 360), (0, 46), (0, 46, 640, 268), id="letterbox"),
        pytest.param((640, 360), (640, 360), (0, 0), (0, 0, 640, 360), id="no-borders"),
    ],
)
def test_active_picture_matches_the_real_bars(
    inner, outer, offset, picture, tmp_path, model_path, monkeypatch
) -> None:
    monkeypatch.setattr(source_analysis, "YuNetFaceDetector", NoFacesDetector)
    source = tmp_path / "bars.mp4"
    make_bordered_video(source, inner=inner, outer=outer, offset=offset, duration=3.0)
    analysis = analyze(source, tmp_path, model_path)
    found = analysis.detections.active_picture
    left, top, width, height = picture

    assert found.x >= left and found.y >= top
    assert found.x + found.width <= left + width
    assert found.y + found.height <= top + height
    assert found.x - left <= 6 and found.y - top <= 6  # tight, not over-trimmed
    assert (left + width) - (found.x + found.width) <= 6
    assert (top + height) - (found.y + found.height) <= 6

    geometry = analysis.crop_path.geometry
    assert geometry.crop_height == found.height // 2 * 2
    assert geometry.min_x >= left and geometry.max_x + geometry.crop_width <= left + width


# --- Caching --------------------------------------------------------------


def test_second_analysis_reuses_every_cache_without_decoding(
    moving_source, tmp_path, model_path, use_box_detector, monkeypatch
) -> None:
    first = analyze(moving_source, tmp_path, model_path)
    forbid_decoding(monkeypatch)
    second = analyze(moving_source, tmp_path, model_path)
    assert second == first
    for name in (DETECTIONS_FILE, SCENES_FILE, TRACKING_FILE, CROP_PATH_FILE):
        assert (tmp_path / "analysis" / name).is_file()


def test_trimming_reads_the_cache_and_never_redetects(
    moving_source, tmp_path, model_path, use_box_detector, monkeypatch
) -> None:
    analysis = analyze(moving_source, tmp_path, model_path)
    forbid_decoding(monkeypatch)
    reloaded = analyze(moving_source, tmp_path, model_path)

    shots = crop_path_for_range(reloaded, 0.8, 2.2)
    assert shots[0].start_time == pytest.approx(0.8)
    assert shots[-1].end_time == pytest.approx(2.2)
    geometry = reloaded.crop_path.geometry
    for t in (0.8, 1.4, 2.2):
        assert crop_x_at(shots, geometry, t) == crop_x_at(analysis.crop_path.shots, geometry, t)

    for start, end in ((-0.1, 1.0), (1.0, 1.0), (2.0, 99.0)):
        with pytest.raises(InvalidInputError):
            crop_path_for_range(reloaded, start, end)


def test_changed_tracking_params_rebuild_tracking_but_reuse_detections(
    moving_source, tmp_path, model_path, use_box_detector, monkeypatch
) -> None:
    analyze(moving_source, tmp_path, model_path)
    detections_file = tmp_path / "analysis" / DETECTIONS_FILE
    stamp = detections_file.stat().st_mtime_ns
    forbid_decoding(monkeypatch)

    params = TrackingParams(min_confidence=0.9)
    again = analyze(moving_source, tmp_path, model_path, tracking_params=params)

    assert again.tracking.params == params
    assert detections_file.stat().st_mtime_ns == stamp
    stored = read_artifact(tmp_path / "analysis" / TRACKING_FILE, type(again.tracking))
    assert stored is not None and stored.params == params


def test_changed_crop_params_rebuild_only_the_crop_path(
    moving_source, tmp_path, model_path, use_box_detector, monkeypatch
) -> None:
    first = analyze(moving_source, tmp_path, model_path)
    forbid_decoding(monkeypatch)
    params = CropParams(dead_zone_ratio=0.3)
    second = analyze(moving_source, tmp_path, model_path, crop_params=params)
    assert second.crop_path.crop_params == params
    assert second.tracking == first.tracking


def test_modified_source_invalidates_the_detection_cache(
    moving_source, tmp_path, model_path, use_box_detector
) -> None:
    first = analyze(moving_source, tmp_path, model_path)
    make_moving_box_video(moving_source, duration=2.4, box=80, start_x=100.0)
    second = analyze(moving_source, tmp_path, model_path)
    assert second.fingerprint != first.fingerprint
    assert second.fingerprint.duration_seconds < first.fingerprint.duration_seconds
    assert len(second.detections.frames) < len(first.detections.frames)


def test_different_model_invalidates_the_detection_cache(
    moving_source, tmp_path, model_path, use_box_detector, monkeypatch
) -> None:
    first = analyze(moving_source, tmp_path, model_path)
    other_model = tmp_path / "other.onnx"
    other_model.write_bytes(b"model-bytes-b")
    second = analyze(moving_source, tmp_path, other_model)
    assert second.detections.config.model_sha256 != first.detections.config.model_sha256

    forbid_decoding(monkeypatch)
    with pytest.raises(AssertionError):
        analyze(moving_source, tmp_path, model_path)  # back to the old model: stale again


@pytest.mark.parametrize(
    "damage",
    [
        pytest.param(lambda text: text[: len(text) // 2], id="truncated"),
        pytest.param(lambda text: "not json at all", id="garbage"),
        pytest.param(lambda text: "", id="empty"),
        pytest.param(
            lambda text: json.dumps({**json.loads(text), "frames": "oops"}), id="wrong-schema"
        ),
        pytest.param(
            lambda text: json.dumps({**json.loads(text), "schema_version": SCHEMA_VERSION + 1}),
            id="schema-version",
        ),
        pytest.param(
            lambda text: json.dumps(
                {**json.loads(text), "frames": list(reversed(json.loads(text)["frames"]))}
            ),
            id="unordered-times",
        ),
    ],
)
def test_damaged_detection_cache_is_rebuilt_not_trusted(
    damage, moving_source, tmp_path, model_path, use_box_detector
) -> None:
    first = analyze(moving_source, tmp_path, model_path)
    path = tmp_path / "analysis" / DETECTIONS_FILE
    path.write_text(damage(path.read_text(encoding="utf-8")), encoding="utf-8")

    again = analyze(moving_source, tmp_path, model_path)

    assert again.detections == first.detections
    repaired = read_artifact(path, DetectionCacheFile)
    assert repaired == first.detections


def test_damaged_tracking_cache_is_rebuilt(
    moving_source, tmp_path, model_path, use_box_detector, monkeypatch
) -> None:
    first = analyze(moving_source, tmp_path, model_path)
    (tmp_path / "analysis" / TRACKING_FILE).write_text("{broken", encoding="utf-8")
    forbid_decoding(monkeypatch)
    assert analyze(moving_source, tmp_path, model_path).tracking == first.tracking


def test_artifact_write_is_atomic(tmp_path, monkeypatch) -> None:
    class Payload(BaseModel):
        value: int

    path = tmp_path / "artifact.json"
    write_artifact(path, Payload(value=1))
    assert json.loads(path.read_text()) == {"value": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["artifact.json"]

    def failing_replace(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(analysis_cache.os, "replace", failing_replace)
    with pytest.raises(OSError):
        write_artifact(path, Payload(value=2))
    assert json.loads(path.read_text()) == {"value": 1}  # the old file is untouched
    assert [p.name for p in tmp_path.iterdir()] == ["artifact.json"]  # no temp left behind


# --- Real model, opt-in ---------------------------------------------------


@pytest.mark.real_video
def test_real_video_with_the_actual_yunet_model(tmp_path) -> None:
    video = os.environ.get("VIDEO_CLIPPER_FACE_TEST_VIDEO")
    if not video or not Path(video).is_file():
        pytest.skip("set VIDEO_CLIPPER_FACE_TEST_VIDEO to a video file to run this check")
    source = tmp_path / "real.mp4"
    shutil.copyfile(video, source)

    analysis = analyze_source(Settings(), source, tmp_path / "analysis")
    geometry = analysis.crop_path.geometry

    assert analysis.detections.frames
    assert any(frame.faces for frame in analysis.detections.frames)
    assert analysis.tracking.tracks
    for shot in analysis.crop_path.shots:
        for keyframe in shot.keyframes:
            assert keyframe.x % 2 == 0
            assert geometry.min_x <= keyframe.x <= geometry.max_x
    assert geometry.crop_width % 2 == 0 and geometry.crop_height % 2 == 0
