"""Find the visible picture inside letterboxed / pillarboxed video.

A column (row) counts as picture when it holds non-black pixels in a large share of the
sampled frames. Using a frequency instead of "ever non-black" keeps burned-in subtitles
or logos that sit inside a black bar from being mistaken for picture.
"""

import math

import numpy as np

from app.schemas.tracking import ActivePicture, ActivePictureParams, ActivePictureReason


def _even_floor(value: float) -> int:
    return math.floor(value) // 2 * 2


def _even_ceil(value: float) -> int:
    ceiling = math.ceil(value)
    return ceiling + ceiling % 2


def full_frame(width: int, height: int, reason: ActivePictureReason) -> ActivePicture:
    return ActivePicture(
        x=0,
        y=0,
        width=max(2, _even_floor(width)),
        height=max(2, _even_floor(height)),
        reason=reason,
    )


def _content_span(fraction: np.ndarray, min_fraction: float) -> tuple[int, int] | None:
    indices = np.flatnonzero(fraction >= min_fraction)
    if indices.size == 0:
        return None
    return int(indices[0]), int(indices[-1]) + 1


def estimate_active_picture(
    column_fraction: np.ndarray,
    row_fraction: np.ndarray,
    *,
    frame_count: int,
    source_width: int,
    source_height: int,
    params: ActivePictureParams,
) -> ActivePicture:
    """Estimate the picture rectangle in source pixels; fall back to the full frame.

    `column_fraction[i]` / `row_fraction[j]` is the share of sampled frames where that
    analysis-frame column / row contained non-black pixels.
    """
    analysis_width = column_fraction.shape[0]
    analysis_height = row_fraction.shape[0]

    if frame_count < params.min_frames:
        return full_frame(source_width, source_height, "insufficient_frames")

    columns = _content_span(column_fraction, params.min_content_fraction)
    rows = _content_span(row_fraction, params.min_content_fraction)
    if columns is None or rows is None:
        return full_frame(source_width, source_height, "no_content")

    left, right = columns
    top, bottom = rows
    # Tiny borders are encoder noise or overscan, not a real letterbox.
    min_cols = params.min_border_ratio * analysis_width
    min_rows = params.min_border_ratio * analysis_height
    inset = params.edge_inset_px
    left = left + inset if left >= min_cols else 0
    right = right - inset if analysis_width - right >= min_cols else analysis_width
    top = top + inset if top >= min_rows else 0
    bottom = bottom - inset if analysis_height - bottom >= min_rows else analysis_height

    if (left, right, top, bottom) == (0, analysis_width, 0, analysis_height):
        return full_frame(source_width, source_height, "no_borders")

    scale_x = source_width / analysis_width
    scale_y = source_height / analysis_height
    x = _even_ceil(left * scale_x)
    y = _even_ceil(top * scale_y)
    width = _even_floor(right * scale_x) - x
    height = _even_floor(bottom * scale_y) - y

    plausible = (
        width >= 2
        and height >= 2
        and width * height >= params.min_area_ratio * source_width * source_height
    )
    if not plausible:
        return full_frame(source_width, source_height, "implausible_region")
    return ActivePicture(x=x, y=y, width=width, height=height, reason="detected_borders")


class ActivePictureAccumulator:
    """Accumulates per-column / per-row content frequency over analysis frames."""

    def __init__(self, frame_width: int, frame_height: int, params: ActivePictureParams) -> None:
        self._params = params
        self._column_hits = np.zeros(frame_width, dtype=np.int64)
        self._row_hits = np.zeros(frame_height, dtype=np.int64)
        self.frame_count = 0

    def add_frame(self, frame_bgr: np.ndarray) -> None:
        # A pixel is "content" when its brightest channel clears the black threshold.
        brightest = frame_bgr.max(axis=2)
        threshold = self._params.luma_threshold
        self._column_hits += brightest.max(axis=0) > threshold
        self._row_hits += brightest.max(axis=1) > threshold
        self.frame_count += 1

    def result(self, source_width: int, source_height: int) -> ActivePicture:
        divisor = max(self.frame_count, 1)
        return estimate_active_picture(
            self._column_hits / divisor,
            self._row_hits / divisor,
            frame_count=self.frame_count,
            source_width=source_width,
            source_height=source_height,
            params=self._params,
        )
