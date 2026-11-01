"""Face detection with OpenCV YuNet. Detection only: no tracking logic lives here."""

import hashlib
import logging
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from app.core.errors import MediaProcessingError
from app.schemas.tracking import FaceBox

logger = logging.getLogger(__name__)

DETECTOR_NAME = "opencv-yunet"
MODEL_NAME = "face_detection_yunet_2023mar.onnx"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[3] / "models" / MODEL_NAME

# YuNet rows are [x, y, w, h, 5 landmark (x, y) pairs, score].
YUNET_ROW_LENGTH = 15
YUNET_SCORE_COLUMN = 14

DEFAULT_SCORE_THRESHOLD = 0.6
DEFAULT_NMS_THRESHOLD = 0.3
DEFAULT_TOP_K = 20


class FaceDetector(Protocol):
    """Anything that maps one analysis frame to faces in source pixels."""

    def detect(self, frame_bgr: np.ndarray) -> list[FaceBox]: ...


def parse_yunet_output(
    raw: np.ndarray | None,
    *,
    scale_x: float,
    scale_y: float,
    source_width: int,
    source_height: int,
) -> list[FaceBox]:
    """Convert YuNet rows (analysis-frame pixels) to source-pixel boxes.

    Boxes are clipped to the source frame; degenerate or non-finite rows are dropped.
    """
    if raw is None or raw.size == 0:
        return []
    if raw.ndim != 2 or raw.shape[1] < YUNET_ROW_LENGTH:
        raise ValueError(f"Unexpected YuNet output shape {raw.shape}")

    faces: list[FaceBox] = []
    for row in raw:
        if not np.all(np.isfinite(row[:4])) or not np.isfinite(row[YUNET_SCORE_COLUMN]):
            continue
        x0 = max(0.0, float(row[0]) * scale_x)
        y0 = max(0.0, float(row[1]) * scale_y)
        x1 = min(float(source_width), (float(row[0]) + float(row[2])) * scale_x)
        y1 = min(float(source_height), (float(row[1]) + float(row[3])) * scale_y)
        if x1 - x0 < 1.0 or y1 - y0 < 1.0:
            continue
        faces.append(
            FaceBox(
                x=round(x0, 2),
                y=round(y0, 2),
                width=round(x1 - x0, 2),
                height=round(y1 - y0, 2),
                confidence=round(min(1.0, max(0.0, float(row[YUNET_SCORE_COLUMN]))), 4),
            )
        )
    return faces


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class YuNetFaceDetector:
    def __init__(
        self,
        model_path: Path,
        *,
        frame_width: int,
        frame_height: int,
        source_width: int,
        source_height: int,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
        nms_threshold: float = DEFAULT_NMS_THRESHOLD,
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        if not model_path.is_file():
            logger.error("YuNet model file is missing")
            raise MediaProcessingError("Face detection is not available on this server.")
        try:
            self._detector = cv2.FaceDetectorYN.create(
                str(model_path),
                "",
                (frame_width, frame_height),
                score_threshold,
                nms_threshold,
                top_k,
            )
        except cv2.error as exc:
            logger.error("YuNet model could not be loaded: %s", exc)
            raise MediaProcessingError("Face detection is not available on this server.") from exc
        self._frame_size = (frame_width, frame_height)
        self._scale_x = source_width / frame_width
        self._scale_y = source_height / frame_height
        self._source_width = source_width
        self._source_height = source_height

    def detect(self, frame_bgr: np.ndarray) -> list[FaceBox]:
        height, width = frame_bgr.shape[:2]
        if (width, height) != self._frame_size:
            raise ValueError("Frame size does not match the detector input size.")
        _, raw = self._detector.detect(frame_bgr)
        return parse_yunet_output(
            raw,
            scale_x=self._scale_x,
            scale_y=self._scale_y,
            source_width=self._source_width,
            source_height=self._source_height,
        )
