"""Lightweight face tracking and primary-subject selection. Pure functions, no OpenCV.

Tracks are built per shot, so an identity never crosses a scene cut. Within a shot,
detections are linked frame to frame by position and size. A track survives short
detection gaps and ends when it is missing for longer than `max_gap_seconds`.

The primary subject is chosen from whole-track salience (how long and how prominently a
face was seen), with hysteresis, so a bystander that merely gets bigger for a moment
does not steal the crop from the established subject.
"""

import bisect
import math
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import groupby

from app.schemas.tracking import (
    FaceBox,
    FrameDetections,
    SubjectSample,
    Track,
    TrackingParams,
    TrackObservation,
)

TIME_EPSILON = 1e-6


@dataclass(slots=True)
class _OpenTrack:
    shot_index: int
    observations: list[TrackObservation] = field(default_factory=list)

    @property
    def last(self) -> TrackObservation:
        return self.observations[-1]


def shot_index_for_time(time: float, cut_times: Sequence[float]) -> int:
    """Shot 0 is before the first cut; a frame exactly at a cut belongs to the new shot."""
    return bisect.bisect_right(cut_times, time + TIME_EPSILON)


def _association_cost(previous: FaceBox, candidate: FaceBox, size_ratio_limit: float) -> float | None:
    """Centre distance in face widths, or None when the sizes are implausibly different."""
    larger = max(previous.width, candidate.width)
    smaller = min(previous.width, candidate.width)
    if larger / smaller > size_ratio_limit:
        return None
    mean_width = (previous.width + candidate.width) / 2.0
    distance = math.hypot(
        previous.center_x - candidate.center_x,
        previous.center_y - candidate.center_y,
    )
    return distance / mean_width


def _gate(missed_samples: int, params: TrackingParams) -> float:
    grown = params.gate_factor + params.gate_growth_per_missed_sample * missed_samples
    return min(params.gate_max_factor, grown)


def track_faces(
    frames: Sequence[FrameDetections],
    cut_times: Sequence[float],
    params: TrackingParams,
    *,
    sample_interval: float,
) -> list[Track]:
    """Link per-frame detections into tracks. Frames must be sorted by time."""
    finished: list[_OpenTrack] = []
    open_tracks: list[_OpenTrack] = []
    current_shot: int | None = None

    for frame in frames:
        shot = shot_index_for_time(frame.time, cut_times)
        if shot != current_shot:
            finished.extend(open_tracks)
            open_tracks = []
            current_shot = shot

        survivors: list[_OpenTrack] = []
        for track in open_tracks:
            if frame.time - track.last.time > params.max_gap_seconds + TIME_EPSILON:
                finished.append(track)
            else:
                survivors.append(track)
        open_tracks = survivors

        detections = [face for face in frame.faces if face.confidence >= params.min_confidence]
        candidates: list[tuple[float, int, int]] = []
        for track_position, track in enumerate(open_tracks):
            missed = max(0, round((frame.time - track.last.time) / sample_interval) - 1)
            gate = _gate(missed, params)
            for detection_position, detection in enumerate(detections):
                cost = _association_cost(track.last.box, detection, params.size_ratio_limit)
                if cost is not None and cost <= gate:
                    candidates.append((cost, track_position, detection_position))
        candidates.sort()

        used_tracks: set[int] = set()
        used_detections: set[int] = set()
        for _, track_position, detection_position in candidates:
            if track_position in used_tracks or detection_position in used_detections:
                continue
            used_tracks.add(track_position)
            used_detections.add(detection_position)
            open_tracks[track_position].observations.append(
                TrackObservation(time=frame.time, box=detections[detection_position])
            )

        for detection_position, detection in enumerate(detections):
            if detection_position not in used_detections:
                open_tracks.append(
                    _OpenTrack(
                        shot_index=shot,
                        observations=[TrackObservation(time=frame.time, box=detection)],
                    )
                )

    finished.extend(open_tracks)
    kept = [track for track in finished if len(track.observations) >= params.min_track_hits]
    kept.sort(key=lambda track: (track.observations[0].time, track.observations[0].box.x))
    return [
        Track(track_id=index, shot_index=track.shot_index, observations=track.observations)
        for index, track in enumerate(kept)
    ]


def track_salience(track: Track, source_height: float) -> float:
    """Total prominence: sum of confidence x face height (as a share of the frame)."""
    return sum(
        observation.box.confidence * observation.box.height / source_height
        for observation in track.observations
    )


def _blend(start: float, end: float, alpha: float) -> float:
    return start + (end - start) * alpha


def _interpolate_box(before: TrackObservation, after: TrackObservation, time: float) -> FaceBox:
    span = after.time - before.time
    alpha = 0.0 if span <= 0 else (time - before.time) / span
    return FaceBox(
        x=_blend(before.box.x, after.box.x, alpha),
        y=_blend(before.box.y, after.box.y, alpha),
        width=_blend(before.box.width, after.box.width, alpha),
        height=_blend(before.box.height, after.box.height, alpha),
        confidence=min(before.box.confidence, after.box.confidence),
    )


def _box_at(track: Track, times: Sequence[float], time: float) -> tuple[FaceBox, bool]:
    """Box at `time` and whether it was actually detected (else interpolated).

    `times` are the track's observation times, precomputed once per track.
    """
    position = bisect.bisect_left(times, time - TIME_EPSILON)
    if position < len(times) and abs(times[position] - time) <= TIME_EPSILON:
        return track.observations[position].box, True
    position = min(max(position, 1), len(times) - 1)
    return (
        _interpolate_box(track.observations[position - 1], track.observations[position], time),
        False,
    )


def _choose_primary(
    live: Sequence[Track],
    incumbent: Track | None,
    salience: dict[int, float],
    switch_ratio: float,
) -> Track | None:
    if not live:
        return None
    best = max(live, key=lambda track: (salience[track.track_id], -track.track_id))
    incumbent_is_live = incumbent is not None and any(
        track.track_id == incumbent.track_id for track in live
    )
    if incumbent is not None and incumbent_is_live:
        if salience[best.track_id] > switch_ratio * salience[incumbent.track_id]:
            return best
        return incumbent
    return best


def select_primary_subject(
    frames: Sequence[FrameDetections],
    tracks: Sequence[Track],
    cut_times: Sequence[float],
    params: TrackingParams,
    *,
    source_height: float,
) -> list[SubjectSample]:
    """One sample per frame: the primary subject's box, interpolated across short gaps."""
    salience = {track.track_id: track_salience(track, source_height) for track in tracks}
    observation_times = {
        track.track_id: [observation.time for observation in track.observations]
        for track in tracks
    }
    tracks_by_shot: dict[int, list[Track]] = {}
    for track in tracks:
        tracks_by_shot.setdefault(track.shot_index, []).append(track)

    samples: list[SubjectSample] = []
    keyed = [(shot_index_for_time(frame.time, cut_times), frame) for frame in frames]
    for shot, group in groupby(keyed, key=lambda item: item[0]):
        pending = deque(sorted(tracks_by_shot.get(shot, []), key=lambda track: track.start_time))
        live: list[Track] = []
        incumbent: Track | None = None
        for _, frame in group:
            while pending and pending[0].start_time <= frame.time + TIME_EPSILON:
                live.append(pending.popleft())
            live = [track for track in live if track.end_time >= frame.time - TIME_EPSILON]
            incumbent = _choose_primary(live, incumbent, salience, params.switch_salience_ratio)
            if incumbent is None:
                samples.append(
                    SubjectSample(
                        time=frame.time, shot_index=shot, track_id=None, state="none", box=None
                    )
                )
                continue
            box, detected = _box_at(incumbent, observation_times[incumbent.track_id], frame.time)
            samples.append(
                SubjectSample(
                    time=frame.time,
                    shot_index=shot,
                    track_id=incumbent.track_id,
                    state="detected" if detected else "interpolated",
                    box=box,
                )
            )
    return samples
