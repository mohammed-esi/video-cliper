import logging
import subprocess
import threading
from pathlib import Path

from app.core.errors import MediaProcessingError

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_active_process: subprocess.Popen[str] | None = None


def ffmpeg_input_argument(path: Path) -> str:
    resolved = path.expanduser().resolve()
    return f"file:{resolved.as_posix()}"


def terminate_active_process() -> None:
    global _active_process
    with _lock:
        process = _active_process
    if process is None:
        return
    if process.poll() is None:
        logger.info("Terminating active ffmpeg process pid=%s", process.pid)
        process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2.0)
    with _lock:
        if _active_process is process:
            _active_process = None


def run_ffmpeg(
    command: list[str],
    *,
    timeout_seconds: float,
    cancelled: threading.Event | None = None,
) -> None:
    global _active_process
    if cancelled and cancelled.is_set():
        raise MediaProcessingError("Video processing was interrupted.")

    with _lock:
        if _active_process is not None and _active_process.poll() is None:
            raise MediaProcessingError("Another FFmpeg process is already running.")

    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        stdin=subprocess.DEVNULL,
    )
    with _lock:
        _active_process = process
    stderr = ""
    try:
        try:
            _, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.communicate(timeout=2.0)
            raise MediaProcessingError(
                "Video processing took too long. Try a shorter video."
            ) from exc
    finally:
        with _lock:
            if _active_process is process:
                _active_process = None

    if cancelled and cancelled.is_set():
        raise MediaProcessingError("Video processing was interrupted.")

    if process.returncode != 0:
        tail = (stderr or "").strip().splitlines()
        logger.warning("ffmpeg failed code=%s stderr_tail=%s", process.returncode, tail[-3:])
        raise MediaProcessingError("We couldn't generate this clip. Please try again.")
