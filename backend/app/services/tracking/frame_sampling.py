"""Decode downscaled, evenly spaced frames from the source with FFmpeg.

FFmpeg does the decoding, rate conversion and scaling; Python only reads raw BGR
frames from FFmpeg's stdout. Sample `i` is stamped `i / sample_fps` on the source
timeline and shows the latest source frame at or before that time, so the picture is
never newer than its stamp and at most one source-frame interval older.

`round=up` is deliberate. The `fps` filter emits the *last* input frame that rounds to a
tick, so the default `round=near` shows content up to half a sample interval (0.1 s at
5 fps) *after* the stamp, which would put the crop slightly ahead of the subject.
`start_time=0` keeps tick 0 at the start of the timeline even when the first video
frame is not at exactly 0.
"""

import logging
import subprocess
import tempfile
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.config import Settings
from app.core.errors import MediaProcessingError
from app.services.ffmpeg_runner import ffmpeg_input_argument

logger = logging.getLogger(__name__)

BYTES_PER_PIXEL = 3
EXIT_WAIT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class SampledFrame:
    index: int
    time: float
    image: np.ndarray  # BGR, shape (height, width, 3), uint8


def sampling_filter(sample_fps: float, frame_width: int, frame_height: int) -> str:
    return (
        f"fps=fps={sample_fps:.6f}:start_time=0:round=up,"
        f"scale={frame_width}:{frame_height}:flags=area"
    )


def build_sampling_command(
    settings: Settings,
    source_path: Path,
    *,
    sample_fps: float,
    frame_width: int,
    frame_height: int,
) -> list[str]:
    video_filter = sampling_filter(sample_fps, frame_width, frame_height)
    return [
        settings.ffmpeg_path,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        ffmpeg_input_argument(source_path),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-vf",
        video_filter,
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]


def _kill(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=EXIT_WAIT_SECONDS)
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg sampling process did not exit after kill")


def iter_sampled_frames(
    settings: Settings,
    source_path: Path,
    *,
    sample_fps: float,
    frame_width: int,
    frame_height: int,
    timeout_seconds: float,
    cancelled: threading.Event | None = None,
) -> Iterator[SampledFrame]:
    command = build_sampling_command(
        settings,
        source_path,
        sample_fps=sample_fps,
        frame_width=frame_width,
        frame_height=frame_height,
    )
    frame_bytes = frame_width * frame_height * BYTES_PER_PIXEL
    timed_out = threading.Event()

    # stderr goes to a file so a chatty FFmpeg can never block on a full pipe.
    with tempfile.TemporaryFile() as stderr_file:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=stderr_file,
        )
        assert process.stdout is not None

        def _on_timeout() -> None:
            timed_out.set()
            process.kill()

        watchdog = threading.Timer(timeout_seconds, _on_timeout)
        watchdog.start()
        reached_eof = False
        index = 0
        try:
            while True:
                if cancelled is not None and cancelled.is_set():
                    raise MediaProcessingError("Video processing was interrupted.")
                raw = process.stdout.read(frame_bytes)
                if len(raw) < frame_bytes:
                    reached_eof = True
                    break
                image = np.frombuffer(raw, dtype=np.uint8).reshape(
                    frame_height, frame_width, BYTES_PER_PIXEL
                )
                yield SampledFrame(index=index, time=index / sample_fps, image=image)
                index += 1
        finally:
            watchdog.cancel()
            process.stdout.close()
            if reached_eof:
                try:
                    process.wait(timeout=EXIT_WAIT_SECONDS)
                except subprocess.TimeoutExpired:
                    _kill(process)
            else:
                _kill(process)

        if timed_out.is_set():
            raise MediaProcessingError("Video analysis took too long. Try a shorter video.")
        if process.returncode != 0:
            stderr_file.seek(0)
            tail = stderr_file.read().decode("utf-8", errors="replace").strip().splitlines()
            logger.warning(
                "ffmpeg sampling failed code=%s frames_read=%s stderr_tail=%s",
                process.returncode,
                index,
                tail[-3:],
            )
            raise MediaProcessingError("We couldn't analyze this video.")
