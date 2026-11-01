"""Persisted shapes for source analysis: detections, scene cuts, tracking, crop path.

Each artifact is a separate JSON file so tracking and smoothing parameters can be
changed without re-decoding the source or re-running face detection.
All coordinates are source-video pixels; all times are source-timeline seconds.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)


class SourceFingerprint(_Frozen):
    """Identity of the analysed file; any change invalidates every cached artifact."""

    size_bytes: int = Field(ge=0)
    mtime_ns: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    duration_seconds: float = Field(gt=0.0)


class FaceBox(_Frozen):
    x: float
    y: float
    width: float = Field(gt=0.0)
    height: float = Field(gt=0.0)
    confidence: float = Field(ge=0.0, le=1.0)

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2.0

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2.0


class FrameDetections(_Frozen):
    time: float = Field(ge=0.0)
    faces: list[FaceBox]


class ActivePictureParams(_Frozen):
    luma_threshold: int = Field(default=24, ge=0, le=255)
    min_content_fraction: float = Field(default=0.4, gt=0.0, le=1.0)
    min_frames: int = Field(default=10, ge=1)
    min_border_ratio: float = Field(default=0.02, ge=0.0, lt=0.5)
    edge_inset_px: int = Field(default=2, ge=0)
    min_area_ratio: float = Field(default=0.35, gt=0.0, le=1.0)


class DetectionConfig(_Frozen):
    detector: str
    model_name: str
    model_sha256: str
    sample_fps: float = Field(gt=0.0)
    analysis_width: int = Field(ge=2)
    analysis_height: int = Field(ge=2)
    score_threshold: float = Field(ge=0.0, le=1.0)
    nms_threshold: float = Field(ge=0.0, le=1.0)
    top_k: int = Field(ge=1)
    active_picture: ActivePictureParams


ActivePictureReason = Literal[
    "detected_borders",
    "no_borders",
    "insufficient_frames",
    "no_content",
    "implausible_region",
]


class ActivePicture(_Frozen):
    """Visible picture rectangle in source pixels (even-aligned)."""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=2)
    height: int = Field(ge=2)
    reason: ActivePictureReason

    @property
    def is_fallback(self) -> bool:
        return self.reason in {"insufficient_frames", "no_content", "implausible_region"}


class DetectionCacheFile(_Frozen):
    schema_version: int
    source: SourceFingerprint
    config: DetectionConfig
    active_picture: ActivePicture
    frames: list[FrameDetections]


class SceneCut(_Frozen):
    time: float = Field(ge=0.0)
    score: float = Field(ge=0.0, le=1.0)


class SceneConfig(_Frozen):
    detector: str
    analysis_width: int = Field(ge=2)
    min_score: float = Field(ge=0.0, le=1.0)


class SceneCutsFile(_Frozen):
    schema_version: int
    source: SourceFingerprint
    config: SceneConfig
    cuts: list[SceneCut]


class TrackingParams(_Frozen):
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    gate_factor: float = Field(default=2.0, gt=0.0)
    gate_growth_per_missed_sample: float = Field(default=0.5, ge=0.0)
    gate_max_factor: float = Field(default=5.0, gt=0.0)
    size_ratio_limit: float = Field(default=2.5, ge=1.0)
    max_gap_seconds: float = Field(default=1.0, gt=0.0)
    min_track_hits: int = Field(default=2, ge=1)
    switch_salience_ratio: float = Field(default=2.0, ge=1.0)
    scene_cut_min_score: float = Field(default=0.3, ge=0.0, le=1.0)
    scene_cut_min_gap_seconds: float = Field(default=0.5, ge=0.0)


class TrackObservation(_Frozen):
    time: float = Field(ge=0.0)
    box: FaceBox


class Track(_Frozen):
    track_id: int = Field(ge=0)
    shot_index: int = Field(ge=0)
    observations: list[TrackObservation]

    @property
    def start_time(self) -> float:
        return self.observations[0].time

    @property
    def end_time(self) -> float:
        return self.observations[-1].time


SubjectState = Literal["detected", "interpolated", "none"]


class SubjectSample(_Frozen):
    """Primary subject at one sample time. `box` is None only when state is "none"."""

    time: float = Field(ge=0.0)
    shot_index: int = Field(ge=0)
    track_id: int | None
    state: SubjectState
    box: FaceBox | None


class TrackingFile(_Frozen):
    schema_version: int
    source: SourceFingerprint
    detection_config: DetectionConfig
    scene_config: SceneConfig
    params: TrackingParams
    cut_times: list[float]
    tracks: list[Track]
    subject: list[SubjectSample]


class CropParams(_Frozen):
    aspect_width: int = Field(default=9, ge=1)
    aspect_height: int = Field(default=16, ge=1)
    dead_zone_ratio: float = Field(default=0.12, ge=0.0, lt=0.5)
    smoothing_sigma_seconds: float = Field(default=0.35, ge=0.0)
    face_margin_ratio: float = Field(default=0.08, ge=0.0, lt=0.5)
    hold_seconds: float = Field(default=1.0, ge=0.0)
    ease_to_center_seconds: float = Field(default=1.0, gt=0.0)


class CropGeometry(_Frozen):
    """Crop rectangle size and the valid range of its left edge, all even integers."""

    active_picture: ActivePicture
    crop_width: int = Field(ge=2)
    crop_height: int = Field(ge=2)
    crop_y: int = Field(ge=0)
    min_x: int = Field(ge=0)
    max_x: int = Field(ge=0)


class CropKeyframe(_Frozen):
    time: float = Field(ge=0.0)
    x: int = Field(ge=0)


class CropShot(_Frozen):
    start_time: float = Field(ge=0.0)
    end_time: float = Field(ge=0.0)
    has_subject: bool
    keyframes: list[CropKeyframe]


class CropPathFile(_Frozen):
    schema_version: int
    source: SourceFingerprint
    tracking_params: TrackingParams
    crop_params: CropParams
    geometry: CropGeometry
    shots: list[CropShot]
