from app.schemas.tracking import FaceBox, FrameDetections, TrackingParams
from app.services.tracking.subject_tracker import (
    select_primary_subject,
    shot_index_for_time,
    track_faces,
)

INTERVAL = 0.2
SOURCE_HEIGHT = 1080.0
PARAMS = TrackingParams()


def face(cx: float, *, cy: float = 400.0, size: float = 100.0, confidence: float = 0.95) -> FaceBox:
    return FaceBox(
        x=cx - size / 2,
        y=cy - size / 2,
        width=size,
        height=size,
        confidence=confidence,
    )


def frames_from(per_frame: list[list[FaceBox]]) -> list[FrameDetections]:
    return [
        FrameDetections(time=round(index * INTERVAL, 6), faces=faces)
        for index, faces in enumerate(per_frame)
    ]


def run(per_frame, cut_times=(), params=PARAMS):
    frames = frames_from(per_frame)
    tracks = track_faces(frames, cut_times, params, sample_interval=INTERVAL)
    subject = select_primary_subject(
        frames, tracks, cut_times, params, source_height=SOURCE_HEIGHT
    )
    return frames, tracks, subject


def test_moving_face_stays_one_track() -> None:
    _, tracks, subject = run([[face(300 + 20 * i)] for i in range(20)])
    assert len(tracks) == 1
    assert len(tracks[0].observations) == 20
    assert {sample.track_id for sample in subject} == {0}
    assert all(sample.state == "detected" for sample in subject)


def test_two_people_are_tracked_separately() -> None:
    left = [face(300 + 5 * i, cy=300) for i in range(20)]
    right = [face(1400 - 5 * i, cy=500) for i in range(20)]
    _, tracks, _ = run([[a, b] for a, b in zip(left, right, strict=True)])
    assert len(tracks) == 2
    assert all(len(track.observations) == 20 for track in tracks)
    first, second = sorted(tracks, key=lambda track: track.observations[0].box.x)
    assert first.observations[-1].box.center_x < 600
    assert second.observations[-1].box.center_x > 1200


def test_larger_newcomer_does_not_steal_the_primary_subject() -> None:
    established = [face(400, size=100)] * 30
    newcomer = [[]] * 10 + [face(1300, size=200)] * 20  # twice as big, half as long
    per_frame = [
        [established[i], *([newcomer[i]] if newcomer[i] else [])] for i in range(30)
    ]
    _, tracks, subject = run(per_frame)
    assert len(tracks) == 2
    primary_ids = {sample.track_id for sample in subject}
    assert len(primary_ids) == 1
    assert all(sample.box.center_x == 400 for sample in subject if sample.box)


def test_overwhelmingly_more_salient_subject_can_take_over() -> None:
    established = [face(400, size=60)] * 30
    dominant = [[]] * 5 + [face(1300, size=400)] * 25
    per_frame = [[established[i], *([dominant[i]] if dominant[i] else [])] for i in range(30)]
    _, _, subject = run(per_frame)
    assert subject[0].box.center_x == 400
    assert subject[-1].box.center_x == 1300


def test_temporary_detection_loss_is_bridged_by_interpolation() -> None:
    per_frame = [[face(300 + 20 * i)] for i in range(20)]
    for lost in (8, 9, 10):  # 0.6 s gap: shorter than max_gap_seconds
        per_frame[lost] = []
    _, tracks, subject = run(per_frame)
    assert len(tracks) == 1
    interpolated = [sample for sample in subject if sample.state == "interpolated"]
    assert [round(sample.time, 1) for sample in interpolated] == [1.6, 1.8, 2.0]
    for sample in interpolated:
        index = round(sample.time / INTERVAL)
        assert sample.box is not None
        assert abs(sample.box.center_x - (300 + 20 * index)) < 1.0
    assert all(sample.track_id == 0 for sample in subject)


def test_subject_that_leaves_is_dropped_and_new_arrival_is_a_new_track() -> None:
    gap = 8  # 1.6 s: longer than max_gap_seconds
    per_frame = (
        [[face(300)] for _ in range(10)]
        + [[] for _ in range(gap)]
        + [[face(320)] for _ in range(10)]
    )
    _, tracks, subject = run(per_frame)
    assert len(tracks) == 2
    states = [sample.state for sample in subject]
    assert states[:10] == ["detected"] * 10
    assert states[12:16] == ["none"] * 4  # well inside the gap, past the bridging window
    assert subject[12].box is None and subject[12].track_id is None
    assert states[-10:] == ["detected"] * 10
    assert subject[0].track_id != subject[-1].track_id


def test_identity_does_not_cross_a_scene_cut() -> None:
    per_frame = [[face(500)] for _ in range(20)]  # same position straight through
    _, joined, _ = run(per_frame)
    _, split, subject = run(per_frame, cut_times=[2.0])
    assert len(joined) == 1
    assert len(split) == 2
    assert [track.shot_index for track in split] == [0, 1]
    assert subject[9].shot_index == 0 and subject[10].shot_index == 1
    assert subject[9].track_id != subject[10].track_id


def test_a_face_jumping_far_starts_a_new_track_instead_of_teleporting() -> None:
    per_frame = [[face(300)]] * 6 + [[face(1500)]] * 6
    _, tracks, _ = run(per_frame)
    assert len(tracks) == 2


def test_implausible_size_change_is_not_linked() -> None:
    per_frame = [[face(400, size=100)]] * 5 + [[face(405, size=400)]] * 5
    _, tracks, _ = run(per_frame)
    assert len(tracks) == 2


def test_single_frame_false_positive_is_ignored() -> None:
    per_frame = [[] for _ in range(10)]
    per_frame[4] = [face(900)]
    _, tracks, subject = run(per_frame)
    assert tracks == []
    assert all(sample.state == "none" for sample in subject)


def test_low_confidence_detections_are_ignored() -> None:
    per_frame = [[face(300, confidence=0.5)] for _ in range(10)]
    _, tracks, _ = run(per_frame)
    assert tracks == []


def test_frames_without_faces_yield_no_subject() -> None:
    _, tracks, subject = run([[] for _ in range(8)])
    assert tracks == []
    assert len(subject) == 8
    assert all(sample.box is None and sample.state == "none" for sample in subject)


def test_shot_index_boundaries() -> None:
    cuts = [2.0, 5.0]
    assert shot_index_for_time(0.0, cuts) == 0
    assert shot_index_for_time(1.999, cuts) == 0
    assert shot_index_for_time(2.0, cuts) == 1  # a frame at the cut belongs to the new shot
    assert shot_index_for_time(5.5, cuts) == 2
    assert shot_index_for_time(3.0, []) == 0
