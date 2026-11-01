import numpy as np
import pytest

from app.schemas.tracking import (
    ActivePicture,
    ActivePictureParams,
    CropParams,
    FaceBox,
    SubjectSample,
)
from app.services.tracking.active_picture import (
    ActivePictureAccumulator,
    estimate_active_picture,
)
from app.services.tracking.crop_geometry import (
    centered_crop_x,
    clamp_crop_x,
    compute_crop_geometry,
    subject_center_bounds,
)
from app.services.tracking.crop_path import (
    apply_dead_zone,
    build_crop_shots,
    build_target_centers,
    crop_x_at,
    gaussian_smooth,
    slice_crop_shots,
)

INTERVAL = 0.2
PARAMS = CropParams()


def picture(x: int, y: int, width: int, height: int) -> ActivePicture:
    return ActivePicture(x=x, y=y, width=width, height=height, reason="detected_borders")


FULL_HD = ActivePicture(x=0, y=0, width=1920, height=1080, reason="no_borders")


def subject(t: float, cx: float | None, *, width: float = 120.0, shot: int = 0) -> SubjectSample:
    if cx is None:
        return SubjectSample(time=t, shot_index=shot, track_id=None, state="none", box=None)
    box = FaceBox(x=cx - width / 2, y=300, width=width, height=width, confidence=0.95)
    return SubjectSample(time=t, shot_index=shot, track_id=0, state="detected", box=box)


def samples_for(centres: list[float | None], *, shot: int = 0, start: float = 0.0):
    return [subject(round(start + i * INTERVAL, 6), cx, shot=shot) for i, cx in enumerate(centres)]


# --- Geometry ---------------------------------------------------------------


def test_crop_is_9_by_16_with_even_dimensions() -> None:
    geometry = compute_crop_geometry(FULL_HD, PARAMS)
    assert (geometry.crop_width, geometry.crop_height) == (608, 1080)
    assert geometry.crop_width / geometry.crop_height == pytest.approx(9 / 16, abs=0.002)
    assert (geometry.min_x, geometry.max_x) == (0, 1312)


@pytest.mark.parametrize("height", [1079, 1081, 719, 361, 2160])
def test_odd_and_unusual_heights_still_give_even_sizes_inside_the_picture(height) -> None:
    active = picture(0, 0, 1920, height)
    geometry = compute_crop_geometry(active, PARAMS)
    assert geometry.crop_width % 2 == 0 and geometry.crop_height % 2 == 0
    assert geometry.crop_height <= height
    assert geometry.crop_y % 2 == 0
    assert geometry.crop_y + geometry.crop_height <= height
    assert geometry.max_x + geometry.crop_width <= 1920


def test_crop_stays_inside_a_pillarboxed_picture() -> None:
    geometry = compute_crop_geometry(picture(246, 0, 1428, 1080), PARAMS)
    assert geometry.min_x == 246
    assert geometry.max_x + geometry.crop_width <= 246 + 1428
    assert clamp_crop_x(-500, geometry) == 246
    assert clamp_crop_x(99999, geometry) == geometry.max_x


def test_crop_stays_inside_a_letterboxed_picture() -> None:
    geometry = compute_crop_geometry(picture(0, 138, 1920, 804), PARAMS)
    assert geometry.crop_height == 804
    assert geometry.crop_y == 138
    assert geometry.crop_width == 452  # 9:16 of the *picture* height, not the full frame


def test_picture_narrower_than_9_16_gets_a_smaller_valid_crop() -> None:
    geometry = compute_crop_geometry(picture(0, 0, 400, 1080), PARAMS)
    assert geometry.crop_width <= 400
    assert geometry.crop_height <= 1080
    assert geometry.crop_width / geometry.crop_height == pytest.approx(9 / 16, abs=0.01)
    assert geometry.min_x <= geometry.max_x


def test_clamp_returns_even_values_inside_bounds() -> None:
    geometry = compute_crop_geometry(FULL_HD, PARAMS)
    for raw in np.linspace(-100, 1500, 400):
        x = clamp_crop_x(float(raw), geometry)
        assert x % 2 == 0
        assert geometry.min_x <= x <= geometry.max_x


def test_centered_crop_is_centred_on_the_picture() -> None:
    geometry = compute_crop_geometry(picture(246, 0, 1428, 1080), PARAMS)
    centre = centered_crop_x(geometry) + geometry.crop_width / 2
    assert centre == pytest.approx(246 + 714, abs=2)


def test_subject_bounds_keep_the_face_inside_with_margin_and_collapse_for_huge_faces() -> None:
    geometry = compute_crop_geometry(FULL_HD, PARAMS)
    low, high = subject_center_bounds(900.0, 120.0, geometry, PARAMS)
    assert high - low == pytest.approx(2 * (304 - 60 - 0.08 * 608))
    low, high = subject_center_bounds(900.0, 700.0, geometry, PARAMS)
    assert low == high == 900.0


# --- Active picture ----------------------------------------------------------


def fractions(width: int, height: int, cols: tuple[int, int], rows: tuple[int, int], level=1.0):
    column = np.zeros(width)
    column[cols[0] : cols[1]] = level
    row = np.zeros(height)
    row[rows[0] : rows[1]] = level
    return column, row


def estimate(column, row, *, frames=100, source=(1920, 1080), params=ActivePictureParams()):
    return estimate_active_picture(
        column, row, frame_count=frames, source_width=source[0], source_height=source[1], params=params
    )


def test_standard_frame_has_no_borders() -> None:
    column, row = fractions(640, 360, (0, 640), (0, 360))
    result = estimate(column, row)
    assert (result.x, result.y, result.width, result.height) == (0, 0, 1920, 1080)
    assert result.reason == "no_borders" and not result.is_fallback


def test_pillarbox_is_detected_and_trimmed_inside_the_picture() -> None:
    column, row = fractions(640, 360, (80, 560), (0, 360))
    result = estimate(column, row)
    assert result.reason == "detected_borders"
    assert 240 <= result.x <= 252  # picture starts at 240; inset keeps us off the edge
    assert result.x % 2 == 0 and result.width % 2 == 0
    assert result.x + result.width <= 1680
    assert result.y == 0 and result.height == 1080


def test_letterbox_is_detected() -> None:
    column, row = fractions(640, 360, (0, 640), (46, 314))
    result = estimate(column, row)
    assert result.reason == "detected_borders"
    assert result.x == 0 and result.width == 1920
    assert result.y >= 138 and result.y + result.height <= 942


def test_tiny_borders_are_treated_as_noise() -> None:
    column, row = fractions(640, 360, (3, 637), (0, 360))
    assert estimate(column, row).reason == "no_borders"


def test_subtitles_inside_a_letterbox_bar_do_not_count_as_picture() -> None:
    column, row = fractions(640, 360, (0, 640), (46, 314))
    row[320:340] = 0.2  # burned-in subtitles in the bottom bar, only some of the time
    result = estimate(column, row)
    assert result.y + result.height <= 942


def test_unusual_wide_aspect_without_borders_is_left_alone() -> None:
    column, row = fractions(840, 360, (0, 840), (0, 360))
    result = estimate(column, row, source=(2520, 1080))
    assert result.reason == "no_borders" and result.width == 2520


def test_too_few_frames_falls_back_to_the_full_frame() -> None:
    column, row = fractions(640, 360, (80, 560), (0, 360))
    result = estimate(column, row, frames=3)
    assert result.reason == "insufficient_frames" and result.is_fallback
    assert (result.width, result.height) == (1920, 1080)


def test_black_video_falls_back_to_the_full_frame() -> None:
    result = estimate(np.zeros(640), np.zeros(360))
    assert result.reason == "no_content" and result.is_fallback


def test_implausibly_small_picture_falls_back_to_the_full_frame() -> None:
    column, row = fractions(640, 360, (300, 340), (150, 210))
    result = estimate(column, row)
    assert result.reason == "implausible_region" and result.is_fallback
    assert (result.width, result.height) == (1920, 1080)


def test_accumulator_finds_pillarbox_from_frames() -> None:
    rng = np.random.default_rng(1)
    accumulator = ActivePictureAccumulator(160, 90, ActivePictureParams())
    for _ in range(20):
        frame = np.zeros((90, 160, 3), dtype=np.uint8)
        frame[:, 20:140] = rng.integers(60, 255, (90, 120, 3), dtype=np.uint8)
        accumulator.add_frame(frame)
    result = accumulator.result(1920, 1080)
    assert result.reason == "detected_borders"
    assert 240 <= result.x <= 276 and result.x + result.width <= 1680


# --- Crop path ---------------------------------------------------------------


def test_targets_hold_then_ease_to_the_picture_centre_when_subject_leaves() -> None:
    centres = [300.0, 300.0] + [None] * 12
    targets = build_target_centers(samples_for(centres), picture_center_x=960.0, params=PARAMS)
    assert targets[:2] == [300.0, 300.0]
    assert targets[2] == 300.0  # still holding (within hold_seconds)
    assert targets[-1] == pytest.approx(960.0)  # eased all the way back
    assert targets[7] < targets[10]  # moving monotonically toward the centre


def test_targets_are_centred_when_no_subject_was_ever_seen() -> None:
    targets = build_target_centers(samples_for([None] * 5), picture_center_x=960.0, params=PARAMS)
    assert targets == [960.0] * 5


def test_dead_zone_ignores_small_movements_and_follows_large_ones_minimally() -> None:
    assert apply_dead_zone([500, 530, 470, 520, 480], dead_zone=40) == [500] * 5
    followed = apply_dead_zone([500, 500, 700], dead_zone=40)
    assert followed == [500, 500, 660]  # moves only as far as needed to keep 40 px


def test_gaussian_smoothing_preserves_constants_and_softens_steps_without_overshoot() -> None:
    assert gaussian_smooth([400.0] * 12, 2.0) == pytest.approx([400.0] * 12)
    stepped = gaussian_smooth([0.0] * 10 + [100.0] * 10, 2.0)
    assert all(0.0 <= value <= 100.0 + 1e-9 for value in stepped)
    assert all(b >= a - 1e-9 for a, b in zip(stepped, stepped[1:], strict=False))
    assert 0.0 < stepped[9] < 100.0 and 0.0 < stepped[10] < 100.0
    assert gaussian_smooth([1.0, 2.0, 3.0], 0.0) == [1.0, 2.0, 3.0]


def shots_for(centres, *, cuts=(), duration=None, active=FULL_HD, shots_samples=None):
    geometry = compute_crop_geometry(active, PARAMS)
    samples = shots_samples or samples_for(centres)
    end = duration if duration is not None else samples[-1].time + INTERVAL
    return geometry, build_crop_shots(
        samples, list(cuts), duration=end, geometry=geometry, params=PARAMS, sample_interval=INTERVAL
    )


def test_small_subject_jitter_causes_no_camera_movement() -> None:
    rng = np.random.default_rng(3)
    centres = [960.0 + float(v) for v in rng.uniform(-25, 25, 60)]
    _, shots = shots_for(centres)
    xs = {keyframe.x for shot in shots for keyframe in shot.keyframes}
    assert max(xs) - min(xs) <= 2


def test_crop_follows_a_moving_subject_instead_of_staying_centred() -> None:
    centres = [300.0 + 40.0 * i for i in range(40)]  # walks from 300 to 1860
    geometry, shots = shots_for(centres)
    first, last = shots[0].keyframes[0].x, shots[0].keyframes[-1].x
    assert last - first > 900
    assert last == geometry.max_x  # reached the right edge of the picture


def test_steady_fast_pan_is_followed_without_losing_the_subject() -> None:
    centres = [200.0 + 200.0 * i for i in range(9)]  # 1000 px/s
    samples = samples_for(centres)
    geometry, shots = shots_for(centres)
    for sample in samples:
        x = crop_x_at(shots, geometry, sample.time)
        assert sample.box is not None
        assert x <= sample.box.x and sample.box.x + sample.box.width <= x + geometry.crop_width


def test_sudden_jump_is_not_smoothed_into_losing_the_subject() -> None:
    # Smoothing alone would take several samples to catch up; the visibility constraint
    # is what lets the crop move as fast as needed.
    centres = [300.0] * 8 + [1500.0] * 8
    samples = samples_for(centres)
    geometry, shots = shots_for(centres)
    for sample in samples:
        x = crop_x_at(shots, geometry, sample.time)
        assert sample.box is not None
        assert x <= sample.box.x and sample.box.x + sample.box.width <= x + geometry.crop_width


def test_no_smoothing_across_scene_cuts() -> None:
    left = samples_for([300.0] * 10, shot=0)
    right = samples_for([1600.0] * 10, shot=1, start=2.0)
    geometry, shots = shots_for(None, cuts=[2.0], duration=4.0, shots_samples=left + right)
    assert len(shots) == 2
    assert {k.x for k in shots[0].keyframes} == {crop_x_at(shots, geometry, 0.0)}
    assert {k.x for k in shots[1].keyframes} == {crop_x_at(shots, geometry, 3.0)}
    before = crop_x_at(shots, geometry, 1.99)
    after = crop_x_at(shots, geometry, 2.0)
    assert after - before > 800  # a hard jump at the cut, no pan across it
    assert shots[1].keyframes[0].time == pytest.approx(2.0)


def test_missing_subject_falls_back_to_a_centred_crop() -> None:
    geometry, shots = shots_for([None] * 10)
    assert not shots[0].has_subject
    assert {k.x for k in shots[0].keyframes} == {centered_crop_x(geometry)}


def test_shot_with_no_samples_still_gets_a_valid_path() -> None:
    geometry, shots = shots_for(None, cuts=[1.0], duration=3.0, shots_samples=samples_for([500.0] * 5, shot=0))
    assert len(shots) == 2
    assert {k.x for k in shots[1].keyframes} == {centered_crop_x(geometry)}


def test_every_crop_position_is_even_and_inside_the_picture() -> None:
    rng = np.random.default_rng(7)
    active = picture(246, 0, 1428, 1080)
    centres = [float(v) for v in rng.uniform(-300, 2300, 120)]  # includes off-picture subjects
    geometry, shots = shots_for(centres, active=active)
    for shot in shots:
        for keyframe in shot.keyframes:
            assert keyframe.x % 2 == 0
            assert geometry.min_x <= keyframe.x <= geometry.max_x
    for t in np.linspace(0, 24, 481):
        x = crop_x_at(shots, geometry, float(t))
        assert x % 2 == 0 and geometry.min_x <= x <= geometry.max_x


def test_slicing_to_an_edited_range_keeps_exact_values_at_the_edges() -> None:
    centres = [300.0 + 30.0 * i for i in range(50)]
    geometry, shots = shots_for(centres)
    sliced = slice_crop_shots(shots, geometry, 2.3, 6.1)
    assert sliced[0].keyframes[0].time == pytest.approx(2.3)
    assert sliced[-1].keyframes[-1].time == pytest.approx(6.1)
    for t in (2.3, 3.0, 4.4, 6.1):
        assert crop_x_at(sliced, geometry, t) == crop_x_at(shots, geometry, t)
    assert all(2.3 - 1e-6 <= k.time <= 6.1 + 1e-6 for s in sliced for k in s.keyframes)


def test_slicing_across_a_cut_keeps_both_shots() -> None:
    left = samples_for([300.0] * 10, shot=0)
    right = samples_for([1600.0] * 10, shot=1, start=2.0)
    geometry, shots = shots_for(None, cuts=[2.0], duration=4.0, shots_samples=left + right)
    sliced = slice_crop_shots(shots, geometry, 1.0, 3.0)
    assert len(sliced) == 2
    assert sliced[0].end_time == pytest.approx(2.0) and sliced[1].start_time == pytest.approx(2.0)
