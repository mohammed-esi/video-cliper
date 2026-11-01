"""Generate small synthetic videos with FFmpeg lavfi sources at test time."""

import shutil
import subprocess
from pathlib import Path

import pytest


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


requires_ffmpeg = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not installed")


def _run_ffmpeg(args: list[str]) -> None:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
        check=True,
        timeout=120,
    )


_ENCODE = ["-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "10", "-preset", "veryfast"]


def make_moving_box_video(
    path: Path,
    *,
    size: tuple[int, int] = (1280, 720),
    duration: float = 4.0,
    fps: int = 25,
    box: int = 80,
    speed_px_per_second: float = 200.0,
    start_x: float = 0.0,
    video_delay: float = 0.0,
) -> None:
    """Black frame with a white square sliding right at a known constant speed.

    With `video_delay` the video stream starts that many seconds late while an audio
    track starts at 0, like real files whose first video frame is not at time 0.
    """
    width, height = size
    overlay = (
        f"[0:v][1:v]overlay=x='{start_x}+t*{speed_px_per_second}':y={height // 2 - box // 2}"
    )
    inputs = [
        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}:d={duration}",
        "-f", "lavfi", "-i", f"color=c=white:s={box}x{box}:r={fps}:d={duration}",
    ]
    if video_delay > 0:
        _run_ffmpeg(
            [
                *inputs,
                "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono:d={duration + video_delay}",
                "-filter_complex", f"{overlay},setpts=PTS+{video_delay}/TB[v]",
                "-map", "[v]", "-map", "2:a",
                *_ENCODE,
                "-c:a", "aac",
                str(path),
            ]
        )
        return
    _run_ffmpeg([*inputs, "-filter_complex", overlay, *_ENCODE, str(path)])


def make_hard_cut_video(
    path: Path,
    *,
    size: tuple[int, int] = (640, 360),
    segment_seconds: float = 2.0,
    fps: int = 25,
) -> None:
    """Two textured segments joined by one hard cut at `segment_seconds`."""
    width, height = size
    _run_ffmpeg(
        [
            "-f", "lavfi", "-i", f"testsrc2=s={width}x{height}:r={fps}:d={segment_seconds}",
            "-f", "lavfi", "-i", f"mandelbrot=s={width}x{height}:r={fps}",
            "-filter_complex",
            f"[1:v]trim=duration={segment_seconds},setpts=PTS-STARTPTS[b];[0:v][b]concat=n=2:v=1:a=0",
            *_ENCODE,
            str(path),
        ]
    )


def make_bordered_video(
    path: Path,
    *,
    inner: tuple[int, int],
    outer: tuple[int, int],
    offset: tuple[int, int],
    duration: float = 3.0,
    fps: int = 25,
) -> None:
    """Textured picture of size `inner` centred in black bars up to size `outer`."""
    inner_width, inner_height = inner
    outer_width, outer_height = outer
    _run_ffmpeg(
        [
            "-f", "lavfi", "-i", f"testsrc2=s={inner_width}x{inner_height}:r={fps}:d={duration}",
            "-vf", f"pad={outer_width}:{outer_height}:{offset[0]}:{offset[1]}:black",
            *_ENCODE,
            str(path),
        ]
    )


def make_jumping_box_video(
    path: Path,
    *,
    size: tuple[int, int] = (1280, 720),
    duration: float = 4.0,
    fps: int = 25,
    box: int = 80,
    jump_time: float = 2.0,
    x_before: int = 100,
    x_after: int = 1000,
) -> None:
    """Black frame whose white square teleports at `jump_time`: motion, but no scene cut."""
    width, height = size
    y = height // 2 - box // 2
    _run_ffmpeg(
        [
            "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}:d={duration}",
            "-f", "lavfi", "-i", f"color=c=white:s={box}x{box}:r={fps}:d={duration}",
            "-filter_complex",
            f"[0:v][1:v]overlay=x='if(lt(t,{jump_time}),{x_before},{x_after})':y={y}",
            *_ENCODE,
            str(path),
        ]
    )
