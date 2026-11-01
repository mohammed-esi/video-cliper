"""Time-based clip segmentation (pure functions, no I/O)."""


def compute_time_segments(
    duration: float,
    *,
    target_length: float = 60.0,
    min_tail_to_merge: float = 10.0,
    min_clip_duration: float = 0.1,
) -> list[tuple[float, float]]:
    """
    Split [0, duration] into non-overlapping [start, end) segments.

    A final segment shorter than min_tail_to_merge is merged into the previous
    clip when possible so we avoid a very short trailing clip.
    """
    if duration <= min_clip_duration:
        return []

    if duration <= target_length:
        return [(0.0, duration)]

    segments: list[tuple[float, float]] = []
    start = 0.0
    while start < duration - min_clip_duration:
        end = min(start + target_length, duration)
        if end - start < min_clip_duration:
            break
        segments.append((start, end))
        start = end

    if len(segments) >= 2:
        last_start, last_end = segments[-1]
        tail = last_end - last_start
        if tail < min_tail_to_merge:
            prev_start, _prev_end = segments[-2]
            segments = segments[:-2] + [(prev_start, last_end)]

    return [
        (segment_start, segment_end)
        for segment_start, segment_end in segments
        if segment_end - segment_start >= min_clip_duration
    ]
