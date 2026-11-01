"""Development-only: render a tracking debug video for a source file.

Usage (from backend/):
    .venv/bin/python -m scripts.debug_tracking PATH_TO_VIDEO [--start 20] [--duration 30]

Writes data/debug/<name>_tracking.mp4 (gitignored) showing, per frame:
  left  - every detected face (yellow), the primary subject (green), the active picture
          (blue), the 9:16 crop (red), and a banner on scene cuts
  right - the crop as it would be framed (low-resolution, no audio: debug only)
  below - subject centre (green) vs crop centre (red) over the rendered window
This is not part of the app and is never served to the frontend.
"""

import argparse
import bisect
import logging
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from app.core.config import Settings
from app.schemas.tracking import ActivePicture, CropGeometry, FaceBox
from app.services.ffmpeg_runner import ffmpeg_input_argument
from app.services.tracking.crop_path import crop_x_at
from app.services.tracking.frame_sampling import sampling_filter
from app.services.tracking.source_analysis import SourceAnalysis, analyze_source

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEBUG_DIR = BACKEND_DIR / "data" / "debug"
STRIP_HEIGHT = 70
YELLOW = (0, 220, 255)
GREEN = (0, 220, 0)
RED = (40, 40, 255)
BLUE = (255, 140, 0)
WHITE = (255, 255, 255)
FONT = cv2.FONT_HERSHEY_SIMPLEX

Point = tuple[int, int]


def _nearest_index(times: list[float], time_value: float) -> int:
    position = bisect.bisect_left(times, time_value)
    if position == 0:
        return 0
    if position >= len(times):
        return len(times) - 1
    before_gap = time_value - times[position - 1]
    after_gap = times[position] - time_value
    return position if after_gap < before_gap else position - 1


def _scaled_corners(x: float, y: float, width: float, height: float, scale: float) -> tuple[Point, Point]:
    return (
        (round(x * scale), round(y * scale)),
        (round((x + width) * scale), round((y + height) * scale)),
    )


def _decode_command(
    settings: Settings, source: Path, start: float, duration: float, fps: int, size: tuple[int, int]
) -> list[str]:
    width, height = size
    return [
        settings.ffmpeg_path, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-protocol_whitelist", "file,pipe",
        "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", ffmpeg_input_argument(source),
        "-an", "-vf", sampling_filter(float(fps), width, height),
        "-pix_fmt", "bgr24", "-f", "rawvideo", "pipe:1",
    ]


def _encode_command(settings: Settings, output: Path, fps: int, size: tuple[int, int]) -> list[str]:
    width, height = size
    return [
        settings.ffmpeg_path, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps),
        "-i", "pipe:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "veryfast",
        "-movflags", "+faststart", str(output),
    ]


def _timeline_strip(
    analysis: SourceAnalysis, start: float, duration: float, width: int, fps: int
) -> np.ndarray:
    """Bottom strip plotting subject centre (green) and crop centre (red) over time."""
    geometry = analysis.crop_path.geometry
    sample_times = [sample.time for sample in analysis.tracking.subject]
    plot_width = width - 20
    plot_height = STRIP_HEIGHT - 10
    scale = plot_width / analysis.fingerprint.width
    frame_count = max(int(duration * fps), 1)

    def point(column: int, centre_x: float) -> Point:
        return column, int(5 + centre_x * scale * plot_height / plot_width)

    strip = np.zeros((STRIP_HEIGHT, width, 3), dtype=np.uint8)
    for frame_index in range(frame_count):
        t = start + frame_index / fps
        column = 10 + int(frame_index / max(frame_count - 1, 1) * plot_width)
        crop_centre = crop_x_at(analysis.crop_path.shots, geometry, t) + geometry.crop_width / 2
        cv2.circle(strip, point(column, crop_centre), 1, RED, -1)
        subject = analysis.tracking.subject[_nearest_index(sample_times, t)]
        if subject.box is not None:
            cv2.circle(strip, point(column, subject.box.center_x), 1, GREEN, -1)
    for cut in analysis.tracking.cut_times:
        if start <= cut < start + duration:
            column = 10 + int((cut - start) / duration * plot_width)
            cv2.line(strip, (column, 0), (column, STRIP_HEIGHT), WHITE, 1)
    return strip


def _draw_face(frame: np.ndarray, box: FaceBox, scale: float, color, thickness: int) -> Point:
    top_left, bottom_right = _scaled_corners(box.x, box.y, box.width, box.height, scale)
    cv2.rectangle(frame, top_left, bottom_right, color, thickness)
    return top_left


def _draw_picture(frame: np.ndarray, active: ActivePicture, scale: float) -> None:
    corners = _scaled_corners(active.x, active.y, active.width, active.height, scale)
    cv2.rectangle(frame, *corners, BLUE, 1)


def _draw_crop(
    frame: np.ndarray, geometry: CropGeometry, crop_x: int, scale: float
) -> tuple[Point, Point]:
    corners = _scaled_corners(
        crop_x, geometry.crop_y, geometry.crop_width, geometry.crop_height, scale
    )
    cv2.rectangle(frame, *corners, RED, 3)
    return corners


def _crop_panel(frame: np.ndarray, corners: tuple[Point, Point], size: tuple[int, int]) -> np.ndarray:
    (left, top), (right, bottom) = corners
    panel = frame[top:bottom, left:right]
    if panel.size == 0:
        return np.zeros((size[1], size[0], 3), dtype=np.uint8)
    return cv2.resize(panel, size, interpolation=cv2.INTER_AREA)


def _finish(process: subprocess.Popen, name: str, timeout: float) -> None:
    code = process.wait(timeout=timeout)
    if code != 0:
        raise RuntimeError(f"ffmpeg {name} exited with status {code}")


def render_debug_video(
    settings: Settings,
    source: Path,
    analysis: SourceAnalysis,
    output: Path,
    start: float,
    duration: float,
    fps: int = 15,
    width: int = 960,
) -> dict[str, float]:
    fingerprint = analysis.fingerprint
    geometry = analysis.crop_path.geometry
    scale = width / fingerprint.width
    height = round(fingerprint.height * scale / 2) * 2
    panel_size = (round(height * 9 / 16 / 2) * 2, height)
    canvas_size = (width + panel_size[0], height + STRIP_HEIGHT)
    strip = _timeline_strip(analysis, start, duration, canvas_size[0], fps)
    strip_columns = max(int(duration * fps) - 1, 1)

    detection_frames = analysis.detections.frames
    detection_times = [frame.time for frame in detection_frames]
    subjects = analysis.tracking.subject
    cut_times = analysis.tracking.cut_times

    output.parent.mkdir(parents=True, exist_ok=True)
    decoder = subprocess.Popen(
        _decode_command(settings, source, start, duration, fps, (width, height)),
        stdout=subprocess.PIPE,
    )
    encoder = subprocess.Popen(
        _encode_command(settings, output, fps, canvas_size), stdin=subprocess.PIPE
    )
    assert decoder.stdout is not None and encoder.stdin is not None

    crop_xs: list[int] = []
    states = {"detected": 0, "interpolated": 0, "none": 0}
    frame_bytes = width * height * 3
    frame_index = 0
    try:
        while len(raw := decoder.stdout.read(frame_bytes)) == frame_bytes:
            frame = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3).copy()
            t = start + frame_index / fps
            index = _nearest_index(detection_times, t)
            crop_x = crop_x_at(analysis.crop_path.shots, geometry, t)
            crop_xs.append(crop_x)

            _draw_picture(frame, geometry.active_picture, scale)
            for face in detection_frames[index].faces:
                _draw_face(frame, face, scale, YELLOW, 1)
            subject = subjects[index]
            states[subject.state] += 1
            if subject.box is not None:
                label_at = _draw_face(frame, subject.box, scale, GREEN, 2)
                label = f"T{subject.track_id} {subject.state}"
                cv2.putText(frame, label, (label_at[0], max(12, label_at[1] - 6)), FONT, 0.5, GREEN, 1)
            crop_corners = _draw_crop(frame, geometry, crop_x, scale)
            if any(0 <= t - cut < 0.4 for cut in cut_times):
                cv2.rectangle(frame, (0, 0), (width - 1, height - 1), WHITE, 6)
                cv2.putText(frame, "SCENE CUT", (12, 56), FONT, 1.0, WHITE, 2)
            cv2.putText(frame, f"t={t:6.2f}s crop_x={crop_x}", (12, 24), FONT, 0.6, WHITE, 2)

            canvas = np.zeros((canvas_size[1], canvas_size[0], 3), dtype=np.uint8)
            canvas[:height, :width] = frame
            canvas[:height, width:] = _crop_panel(frame, crop_corners, panel_size)
            canvas[height:] = strip
            cursor = 10 + int(frame_index / strip_columns * (canvas_size[0] - 20))
            cv2.line(canvas, (cursor, height), (cursor, canvas_size[1]), WHITE, 1)
            encoder.stdin.write(canvas.tobytes())
            frame_index += 1
    finally:
        decoder.stdout.close()
        encoder.stdin.close()
    _finish(decoder, "decoder", 30)
    _finish(encoder, "encoder", 120)

    xs = np.asarray(crop_xs, dtype=float)
    steps = np.abs(np.diff(xs)) if xs.size > 1 else np.zeros(1)
    return {
        "frames": float(frame_index),
        "crop_x_min": float(xs.min()) if xs.size else 0.0,
        "crop_x_max": float(xs.max()) if xs.size else 0.0,
        "mean_abs_step_px": float(steps.mean()),
        "max_abs_step_px": float(steps.max()),
        **{f"samples_{name}": float(count) for name, count in states.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--analysis-dir", type=Path)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings()
    source = args.video.expanduser().resolve()
    name = source.parent.name if source.name.startswith("source.") else source.stem
    analysis_dir = args.analysis_dir or DEBUG_DIR / name / "analysis"
    output = args.output or DEBUG_DIR / f"{name}_tracking.mp4"

    started = time.monotonic()
    analysis = analyze_source(settings, source, analysis_dir)
    analysed = time.monotonic() - started
    duration = min(args.duration, analysis.fingerprint.duration_seconds - args.start)
    stats = render_debug_video(settings, source, analysis, output, args.start, duration)
    print(f"analysis_seconds={analysed:.1f} (cached runs are near-instant)")
    print(f"active_picture={analysis.detections.active_picture}")
    print(
        f"scene_cuts_applied={len(analysis.tracking.cut_times)} "
        f"tracks={len(analysis.tracking.tracks)}"
    )
    for key, value in stats.items():
        print(f"{key}={value:.1f}")
    print(f"debug_video={output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
