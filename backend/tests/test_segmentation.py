from app.services.segmentation import compute_time_segments


def test_single_clip_when_shorter_than_target() -> None:
    assert compute_time_segments(25.0, target_length=30.0) == [(0.0, 25.0)]


def test_even_splits_for_long_video() -> None:
    segments = compute_time_segments(90.0, target_length=30.0, min_tail_to_merge=10.0)
    assert segments == [(0.0, 30.0), (30.0, 60.0), (60.0, 90.0)]


def test_merges_short_final_segment() -> None:
    segments = compute_time_segments(65.0, target_length=30.0, min_tail_to_merge=10.0)
    assert segments == [(0.0, 30.0), (30.0, 65.0)]


def test_no_zero_duration_segments() -> None:
    segments = compute_time_segments(0.05, target_length=30.0)
    assert segments == []
