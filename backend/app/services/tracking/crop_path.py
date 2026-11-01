"""Offline horizontal crop trajectory from the primary-subject track. Pure functions.

Per shot (never smoothing across a scene cut):
1. Target centre: the subject's centre; hold the last position briefly after the subject
   truly disappears, then ease back to the picture centre; centre when never seen.
2. Dead-zone follower: the crop stays still while the subject drifts inside a comfort
   band and only moves as far as needed once the subject leaves it.
3. Zero-phase Gaussian smoothing (possible because the whole clip is known in advance).
4. Visibility constraint: smoothing may lag a fast mover, so the centre is finally
   clamped to keep the subject's face inside the crop. This is what allows fast pans
   when needed without imposing a speed limit.
5. Clamp to the active picture and quantise to even pixels.
"""

import bisect
import math
from collections.abc import Sequence
from itertools import groupby

import numpy as np

from app.schemas.tracking import (
    CropGeometry,
    CropKeyframe,
    CropParams,
    CropShot,
    SubjectSample,
)
from app.services.tracking.crop_geometry import (
    center_to_left,
    centered_crop_x,
    clamp_crop_x,
    subject_center_bounds,
)

TIME_EPSILON = 1e-6


def _smoothstep(progress: float) -> float:
    progress = min(max(progress, 0.0), 1.0)
    return progress * progress * (3.0 - 2.0 * progress)


def build_target_centers(
    samples: Sequence[SubjectSample],
    *,
    picture_center_x: float,
    params: CropParams,
) -> list[float]:
    """Desired crop centre per sample, before any smoothing."""
    targets: list[float] = []
    last_center: float | None = None
    last_time = 0.0
    for sample in samples:
        if sample.box is not None:
            last_center = sample.box.center_x
            last_time = sample.time
            targets.append(last_center)
            continue
        if last_center is None:
            targets.append(picture_center_x)
            continue
        elapsed = sample.time - last_time
        if elapsed <= params.hold_seconds:
            targets.append(last_center)
            continue
        weight = _smoothstep((elapsed - params.hold_seconds) / params.ease_to_center_seconds)
        targets.append(last_center * (1.0 - weight) + picture_center_x * weight)
    return targets


def apply_dead_zone(targets: Sequence[float], dead_zone: float) -> list[float]:
    """Move only as far as needed to keep each target within `dead_zone` of the crop."""
    if not targets:
        return []
    current = targets[0]
    path = [current]
    for target in targets[1:]:
        if target - current > dead_zone:
            current = target - dead_zone
        elif current - target > dead_zone:
            current = target + dead_zone
        path.append(current)
    return path


def gaussian_smooth(values: Sequence[float], sigma_samples: float) -> list[float]:
    """Zero-phase Gaussian smoothing with edge replication (no lag, no wrap-around)."""
    if sigma_samples <= 0 or len(values) < 2:
        return list(values)
    radius = max(1, math.ceil(3.0 * sigma_samples))
    offsets = np.arange(-radius, radius + 1)
    kernel = np.exp(-0.5 * (offsets / sigma_samples) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(np.asarray(values, dtype=float), radius, mode="edge")
    return np.convolve(padded, kernel, mode="valid").tolist()


def constrain_to_subject(
    centers: Sequence[float],
    samples: Sequence[SubjectSample],
    geometry: CropGeometry,
    params: CropParams,
) -> list[float]:
    """Pull each centre back just enough to keep the subject's face inside the crop."""
    constrained: list[float] = []
    for center, sample in zip(centers, samples, strict=True):
        if sample.box is None:
            constrained.append(center)
            continue
        low, high = subject_center_bounds(
            sample.box.center_x, sample.box.width, geometry, params
        )
        constrained.append(min(max(center, low), high))
    return constrained


def _shot_keyframes(
    samples: Sequence[SubjectSample],
    *,
    shot_start: float,
    shot_end: float,
    geometry: CropGeometry,
    params: CropParams,
    sample_interval: float,
) -> list[CropKeyframe]:
    if not samples:
        x = centered_crop_x(geometry)
        return [CropKeyframe(time=shot_start, x=x), CropKeyframe(time=shot_end, x=x)]

    active = geometry.active_picture
    picture_center = active.x + active.width / 2.0
    targets = build_target_centers(samples, picture_center_x=picture_center, params=params)
    followed = apply_dead_zone(targets, params.dead_zone_ratio * geometry.crop_width)
    smoothed = gaussian_smooth(followed, params.smoothing_sigma_seconds / sample_interval)
    constrained = constrain_to_subject(smoothed, samples, geometry, params)
    positions = [
        clamp_crop_x(center_to_left(center, geometry), geometry) for center in constrained
    ]

    points = [
        (min(max(sample.time, shot_start), shot_end), x)
        for sample, x in zip(samples, positions, strict=True)
    ]
    if points[0][0] > shot_start + TIME_EPSILON:
        points.insert(0, (shot_start, points[0][1]))
    if points[-1][0] < shot_end - TIME_EPSILON:
        points.append((shot_end, points[-1][1]))

    keyframes: list[CropKeyframe] = []
    for time, x in points:
        if keyframes and time - keyframes[-1].time <= TIME_EPSILON:
            keyframes[-1] = CropKeyframe(time=keyframes[-1].time, x=x)
        else:
            keyframes.append(CropKeyframe(time=time, x=x))
    return keyframes


def build_crop_shots(
    samples: Sequence[SubjectSample],
    cut_times: Sequence[float],
    *,
    duration: float,
    geometry: CropGeometry,
    params: CropParams,
    sample_interval: float,
) -> list[CropShot]:
    """One CropShot per shot; smoothing never crosses a cut."""
    boundaries = [0.0, *cut_times, duration]
    by_shot = {
        shot: list(group)
        for shot, group in groupby(samples, key=lambda sample: sample.shot_index)
    }
    shots: list[CropShot] = []
    for shot_index in range(len(boundaries) - 1):
        shot_start, shot_end = boundaries[shot_index], boundaries[shot_index + 1]
        shot_samples = by_shot.get(shot_index, [])
        shots.append(
            CropShot(
                start_time=shot_start,
                end_time=shot_end,
                has_subject=any(sample.box is not None for sample in shot_samples),
                keyframes=_shot_keyframes(
                    shot_samples,
                    shot_start=shot_start,
                    shot_end=shot_end,
                    geometry=geometry,
                    params=params,
                    sample_interval=sample_interval,
                ),
            )
        )
    return shots


def _find_shot(shots: Sequence[CropShot], time: float) -> CropShot:
    starts = [shot.start_time for shot in shots]
    position = bisect.bisect_right(starts, time + TIME_EPSILON) - 1
    return shots[min(max(position, 0), len(shots) - 1)]


def _interpolate_x(keyframes: Sequence[CropKeyframe], time: float) -> float:
    times = [keyframe.time for keyframe in keyframes]
    position = bisect.bisect_right(times, time)
    if position == 0:
        return float(keyframes[0].x)
    if position >= len(keyframes):
        return float(keyframes[-1].x)
    before, after = keyframes[position - 1], keyframes[position]
    span = after.time - before.time
    alpha = 0.0 if span <= 0 else (time - before.time) / span
    return before.x + (after.x - before.x) * alpha


def crop_x_at(shots: Sequence[CropShot], geometry: CropGeometry, time: float) -> int:
    """Crop left edge at `time`: linear between keyframes, jumping only at shot cuts."""
    shot = _find_shot(shots, time)
    return clamp_crop_x(_interpolate_x(shot.keyframes, time), geometry)


def slice_crop_shots(
    shots: Sequence[CropShot],
    geometry: CropGeometry,
    start_time: float,
    end_time: float,
) -> list[CropShot]:
    """Crop path for an edited clip range, with exact keyframes at both range edges."""
    sliced: list[CropShot] = []
    for shot in shots:
        begin = max(shot.start_time, start_time)
        finish = min(shot.end_time, end_time)
        if finish - begin <= TIME_EPSILON:
            continue
        interior = [
            keyframe
            for keyframe in shot.keyframes
            if begin + TIME_EPSILON < keyframe.time < finish - TIME_EPSILON
        ]
        keyframes = [
            CropKeyframe(time=begin, x=crop_x_at([shot], geometry, begin)),
            *interior,
            CropKeyframe(time=finish, x=crop_x_at([shot], geometry, finish)),
        ]
        sliced.append(
            CropShot(
                start_time=begin,
                end_time=finish,
                has_subject=shot.has_subject,
                keyframes=keyframes,
            )
        )
    return sliced
