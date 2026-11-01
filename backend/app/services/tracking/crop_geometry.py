"""9:16 crop rectangle geometry inside the active picture. Pure functions.

Every size and offset is an even integer (required by yuv420p / H.264), and the crop
always lies fully inside the active picture.
"""

import math

from app.schemas.tracking import ActivePicture, CropGeometry, CropParams


def _even_floor(value: float) -> int:
    return math.floor(value) // 2 * 2


def _even_ceil(value: float) -> int:
    ceiling = math.ceil(value)
    return ceiling + ceiling % 2


def _even_round(value: float) -> int:
    return round(value / 2.0) * 2


def compute_crop_geometry(active: ActivePicture, params: CropParams) -> CropGeometry:
    """Largest 9:16 rectangle that fits the active picture, centred vertically.

    Normally the crop uses the full active height. When the picture is narrower than
    9:16 (a portrait or near-square source) the width is the limit instead, so the
    result is still a valid 9:16 crop rather than an out-of-bounds one.
    """
    aspect = params.aspect_width / params.aspect_height
    crop_height = _even_floor(active.height)
    crop_width = _even_round(crop_height * aspect)
    if crop_width > active.width:
        crop_width = _even_floor(active.width)
        crop_height = min(_even_floor(crop_width / aspect), _even_floor(active.height))
    crop_width = max(2, crop_width)
    crop_height = max(2, crop_height)

    min_x = _even_ceil(active.x)
    max_x = _even_floor(active.x + active.width - crop_width)
    crop_y = _even_ceil(active.y) + _even_floor((active.height - crop_height) / 2.0)
    return CropGeometry(
        active_picture=active,
        crop_width=crop_width,
        crop_height=crop_height,
        crop_y=crop_y,
        min_x=min_x,
        max_x=max(min_x, max_x),
    )


def clamp_crop_x(x: float, geometry: CropGeometry) -> int:
    """Nearest valid crop left edge: even and inside [min_x, max_x] (both even)."""
    clamped = min(max(x, geometry.min_x), geometry.max_x)
    return min(max(_even_round(clamped), geometry.min_x), geometry.max_x)


def center_to_left(center_x: float, geometry: CropGeometry) -> float:
    return center_x - geometry.crop_width / 2.0


def centered_crop_x(geometry: CropGeometry) -> int:
    active = geometry.active_picture
    return clamp_crop_x(center_to_left(active.x + active.width / 2.0, geometry), geometry)


def subject_center_bounds(
    face_center_x: float,
    face_width: float,
    geometry: CropGeometry,
    params: CropParams,
) -> tuple[float, float]:
    """Range of crop centres that keep the whole face (plus margin) inside the crop.

    Collapses to the face centre when the face is wider than the crop allows.
    """
    allowed_offset = (
        geometry.crop_width / 2.0
        - face_width / 2.0
        - params.face_margin_ratio * geometry.crop_width
    )
    allowed_offset = max(0.0, allowed_offset)
    return face_center_x - allowed_offset, face_center_x + allowed_offset
