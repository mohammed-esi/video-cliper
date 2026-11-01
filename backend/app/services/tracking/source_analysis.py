"""Source-level analysis: detect once, cache, then derive tracking and crop path.

Stages, each cached in its own file and rebuilt only when stale:
  detections.json (expensive: decode + YuNet)   -> keyed by source + detector config
  scenes.json     (FFmpeg decode)               -> keyed by source + scene config
  tracking.json   (cheap, pure Python)          -> keyed by the above + tracking params
  crop_path.json  (cheap, pure Python)          -> keyed by the above + crop params

Trimming a clip never invalidates any of these: the clip's crop path is a slice of the
whole-source path (`crop_path_for_range`).
"""

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.core.errors import InvalidInputError, MediaProcessingError
from app.schemas.tracking import (
    SCHEMA_VERSION,
    ActivePictureParams,
    CropGeometry,
    CropParams,
    CropPathFile,
    CropShot,
    DetectionCacheFile,
    DetectionConfig,
    FrameDetections,
    SceneConfig,
    SceneCutsFile,
    SourceFingerprint,
    TrackingFile,
    TrackingParams,
)
from app.services.ffprobe import run_ffprobe
from app.services.tracking import scene_cuts
from app.services.tracking.active_picture import ActivePictureAccumulator
from app.services.tracking.analysis_cache import (
    CROP_PATH_FILE,
    DETECTIONS_FILE,
    SCENES_FILE,
    TRACKING_FILE,
    fingerprint_source,
    read_artifact,
    write_artifact,
)
from app.services.tracking.crop_geometry import compute_crop_geometry
from app.services.tracking.crop_path import build_crop_shots, slice_crop_shots
from app.services.tracking.face_detector import (
    DEFAULT_MODEL_PATH,
    DEFAULT_NMS_THRESHOLD,
    DEFAULT_SCORE_THRESHOLD,
    DEFAULT_TOP_K,
    DETECTOR_NAME,
    MODEL_NAME,
    YuNetFaceDetector,
    file_sha256,
)
from app.services.tracking.frame_sampling import iter_sampled_frames
from app.services.tracking.subject_tracker import select_primary_subject, track_faces

logger = logging.getLogger(__name__)

SAMPLE_FPS = 5.0
MAX_ANALYSIS_WIDTH = 640


@dataclass(frozen=True, slots=True)
class SourceAnalysis:
    fingerprint: SourceFingerprint
    detections: DetectionCacheFile
    scenes: SceneCutsFile
    tracking: TrackingFile
    crop_path: CropPathFile


def analysis_frame_size(source_width: int, source_height: int) -> tuple[int, int]:
    """Downscaled even-sized analysis frame; never upscales a small source."""
    width = min(MAX_ANALYSIS_WIDTH, source_width) // 2 * 2
    height = max(2, round(width * source_height / source_width / 2.0) * 2)
    return max(2, width), height


def build_detection_config(model_path: Path, fingerprint: SourceFingerprint) -> DetectionConfig:
    width, height = analysis_frame_size(fingerprint.width, fingerprint.height)
    return DetectionConfig(
        detector=DETECTOR_NAME,
        model_name=MODEL_NAME,
        model_sha256=file_sha256(model_path),
        sample_fps=SAMPLE_FPS,
        analysis_width=width,
        analysis_height=height,
        score_threshold=DEFAULT_SCORE_THRESHOLD,
        nms_threshold=DEFAULT_NMS_THRESHOLD,
        top_k=DEFAULT_TOP_K,
        active_picture=ActivePictureParams(),
    )


def build_scene_config() -> SceneConfig:
    return SceneConfig(
        detector=scene_cuts.DETECTOR_NAME,
        analysis_width=scene_cuts.ANALYSIS_WIDTH,
        min_score=scene_cuts.CANDIDATE_MIN_SCORE,
    )


def _run_detection_pass(
    settings: Settings,
    source_path: Path,
    model_path: Path,
    fingerprint: SourceFingerprint,
    config: DetectionConfig,
    cancelled: threading.Event | None,
) -> DetectionCacheFile:
    detector = YuNetFaceDetector(
        model_path,
        frame_width=config.analysis_width,
        frame_height=config.analysis_height,
        source_width=fingerprint.width,
        source_height=fingerprint.height,
        score_threshold=config.score_threshold,
        nms_threshold=config.nms_threshold,
        top_k=config.top_k,
    )
    accumulator = ActivePictureAccumulator(
        config.analysis_width, config.analysis_height, config.active_picture
    )
    frames: list[FrameDetections] = []
    for sampled in iter_sampled_frames(
        settings,
        source_path,
        sample_fps=config.sample_fps,
        frame_width=config.analysis_width,
        frame_height=config.analysis_height,
        timeout_seconds=settings.analysis_timeout_seconds,
        cancelled=cancelled,
    ):
        accumulator.add_frame(sampled.image)
        frames.append(
            FrameDetections(time=round(sampled.time, 6), faces=detector.detect(sampled.image))
        )
    if not frames:
        logger.warning("Face sampling produced no frames")
        raise MediaProcessingError("We couldn't analyze this video.")
    return DetectionCacheFile(
        schema_version=SCHEMA_VERSION,
        source=fingerprint,
        config=config,
        active_picture=accumulator.result(fingerprint.width, fingerprint.height),
        frames=frames,
    )


def _detections_are_current(
    cache: DetectionCacheFile, fingerprint: SourceFingerprint, config: DetectionConfig
) -> bool:
    if (
        cache.schema_version != SCHEMA_VERSION
        or cache.source != fingerprint
        or cache.config != config
        or not cache.frames
    ):
        return False
    times = [frame.time for frame in cache.frames]
    return all(later > earlier for earlier, later in zip(times, times[1:], strict=False))


def load_or_build_detections(
    settings: Settings,
    source_path: Path,
    analysis_dir: Path,
    fingerprint: SourceFingerprint,
    *,
    model_path: Path = DEFAULT_MODEL_PATH,
    cancelled: threading.Event | None = None,
) -> DetectionCacheFile:
    config = build_detection_config(model_path, fingerprint)
    path = analysis_dir / DETECTIONS_FILE
    cached = read_artifact(path, DetectionCacheFile)
    if cached is not None and _detections_are_current(cached, fingerprint, config):
        return cached
    started = time.monotonic()
    built = _run_detection_pass(settings, source_path, model_path, fingerprint, config, cancelled)
    write_artifact(path, built)
    logger.info(
        "Built face detection cache frames=%s seconds=%.1f",
        len(built.frames),
        time.monotonic() - started,
    )
    return built


def load_or_build_scene_cuts(
    settings: Settings,
    source_path: Path,
    analysis_dir: Path,
    fingerprint: SourceFingerprint,
) -> SceneCutsFile:
    config = build_scene_config()
    path = analysis_dir / SCENES_FILE
    cached = read_artifact(path, SceneCutsFile)
    if (
        cached is not None
        and cached.schema_version == SCHEMA_VERSION
        and cached.source == fingerprint
        and cached.config == config
    ):
        return cached
    started = time.monotonic()
    built = SceneCutsFile(
        schema_version=SCHEMA_VERSION,
        source=fingerprint,
        config=config,
        cuts=scene_cuts.detect_scene_cuts(
            settings, source_path, timeout_seconds=settings.analysis_timeout_seconds
        ),
    )
    write_artifact(path, built)
    logger.info(
        "Built scene cut cache candidates=%s seconds=%.1f",
        len(built.cuts),
        time.monotonic() - started,
    )
    return built


def build_tracking(
    detections: DetectionCacheFile, scenes: SceneCutsFile, params: TrackingParams
) -> TrackingFile:
    fingerprint = detections.source
    cut_times = [
        cut_time
        for cut_time in scene_cuts.filter_scene_cuts(
            scenes.cuts,
            min_score=params.scene_cut_min_score,
            min_gap_seconds=params.scene_cut_min_gap_seconds,
        )
        # A cut right at the end would create a zero-length final shot.
        if cut_time < fingerprint.duration_seconds - params.scene_cut_min_gap_seconds
    ]
    interval = 1.0 / detections.config.sample_fps
    tracks = track_faces(detections.frames, cut_times, params, sample_interval=interval)
    subject = select_primary_subject(
        detections.frames,
        tracks,
        cut_times,
        params,
        source_height=float(fingerprint.height),
    )
    return TrackingFile(
        schema_version=SCHEMA_VERSION,
        source=fingerprint,
        detection_config=detections.config,
        scene_config=scenes.config,
        params=params,
        cut_times=cut_times,
        tracks=tracks,
        subject=subject,
    )


def load_or_build_tracking(
    analysis_dir: Path,
    detections: DetectionCacheFile,
    scenes: SceneCutsFile,
    params: TrackingParams,
) -> TrackingFile:
    path = analysis_dir / TRACKING_FILE
    cached = read_artifact(path, TrackingFile)
    if (
        cached is not None
        and cached.schema_version == SCHEMA_VERSION
        and cached.source == detections.source
        and cached.detection_config == detections.config
        and cached.scene_config == scenes.config
        and cached.params == params
        and len(cached.subject) == len(detections.frames)
    ):
        return cached
    built = build_tracking(detections, scenes, params)
    write_artifact(path, built)
    return built


def build_crop_path(
    detections: DetectionCacheFile, tracking: TrackingFile, params: CropParams
) -> CropPathFile:
    geometry = compute_crop_geometry(detections.active_picture, params)
    shots = build_crop_shots(
        tracking.subject,
        tracking.cut_times,
        duration=detections.source.duration_seconds,
        geometry=geometry,
        params=params,
        sample_interval=1.0 / detections.config.sample_fps,
    )
    return CropPathFile(
        schema_version=SCHEMA_VERSION,
        source=detections.source,
        tracking_params=tracking.params,
        crop_params=params,
        geometry=geometry,
        shots=shots,
    )


def load_or_build_crop_path(
    analysis_dir: Path,
    detections: DetectionCacheFile,
    tracking: TrackingFile,
    params: CropParams,
) -> CropPathFile:
    path = analysis_dir / CROP_PATH_FILE
    cached = read_artifact(path, CropPathFile)
    expected_geometry: CropGeometry = compute_crop_geometry(detections.active_picture, params)
    if (
        cached is not None
        and cached.schema_version == SCHEMA_VERSION
        and cached.source == detections.source
        and cached.tracking_params == tracking.params
        and cached.crop_params == params
        and cached.geometry == expected_geometry
        and len(cached.shots) == len(tracking.cut_times) + 1
    ):
        return cached
    built = build_crop_path(detections, tracking, params)
    write_artifact(path, built)
    return built


def analyze_source(
    settings: Settings,
    source_path: Path,
    analysis_dir: Path,
    *,
    model_path: Path = DEFAULT_MODEL_PATH,
    tracking_params: TrackingParams | None = None,
    crop_params: CropParams | None = None,
    cancelled: threading.Event | None = None,
) -> SourceAnalysis:
    """Detect, track and plan the crop for a whole source, reusing any valid cache."""
    probe = run_ffprobe(source_path, settings)
    fingerprint = fingerprint_source(source_path, probe)
    detections = load_or_build_detections(
        settings, source_path, analysis_dir, fingerprint, model_path=model_path, cancelled=cancelled
    )
    scenes = load_or_build_scene_cuts(settings, source_path, analysis_dir, fingerprint)
    tracking = load_or_build_tracking(
        analysis_dir, detections, scenes, tracking_params or TrackingParams()
    )
    crop_path = load_or_build_crop_path(
        analysis_dir, detections, tracking, crop_params or CropParams()
    )
    return SourceAnalysis(
        fingerprint=fingerprint,
        detections=detections,
        scenes=scenes,
        tracking=tracking,
        crop_path=crop_path,
    )


def crop_path_for_range(
    analysis: SourceAnalysis, start_time: float, end_time: float
) -> list[CropShot]:
    """Crop path for an edited clip range. Reads cached analysis only; never decodes."""
    duration = analysis.fingerprint.duration_seconds
    if not 0.0 <= start_time < end_time <= duration + 1e-6:
        raise InvalidInputError("The clip range is outside the video.")
    return slice_crop_shots(
        analysis.crop_path.shots, analysis.crop_path.geometry, start_time, end_time
    )
