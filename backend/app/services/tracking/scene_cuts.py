"""Scene-cut detection from actual frame content (FFmpeg `select` scene score).

The score is FFmpeg's normalised frame-to-frame difference of the *picture*, so a face
moving across a static shot does not register as a cut. Candidates above a low score are
cached; the tracking stage applies the final threshold and minimum gap, so those can be
tuned without decoding the video again.
"""

import logging
import re
import subprocess
from pathlib import Path

from app.core.config import Settings
from app.core.errors import MediaProcessingError
from app.schemas.tracking import SceneCut
from app.services.ffmpeg_runner import ffmpeg_input_argument

logger = logging.getLogger(__name__)

DETECTOR_NAME = "ffmpeg-select-scene"
ANALYSIS_WIDTH = 320
CANDIDATE_MIN_SCORE = 0.15

_PTS_TIME = re.compile(r"pts_time:(?P<time>[0-9]+(?:\.[0-9]+)?)")
_SCENE_SCORE = re.compile(r"lavfi\.scene_score=(?P<score>[0-9]+(?:\.[0-9]+)?)")


def build_scene_command(
    settings: Settings,
    source_path: Path,
    *,
    analysis_width: int = ANALYSIS_WIDTH,
    min_score: float = CANDIDATE_MIN_SCORE,
) -> list[str]:
    # Scale first: the score is resolution-insensitive and this makes decoding-bound
    # filtering several times cheaper.
    video_filter = (
        f"scale={analysis_width}:-2,"
        f"select='gt(scene,{min_score:.4f})',"
        "metadata=mode=print:file=-"
    )
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
        "-f",
        "null",
        "-",
    ]


def parse_scene_metadata(text: str) -> list[SceneCut]:
    """Pair each `pts_time` line with the `scene_score` line that follows it."""
    cuts: list[SceneCut] = []
    pending_time: float | None = None
    for line in text.splitlines():
        time_match = _PTS_TIME.search(line)
        if time_match:
            pending_time = float(time_match.group("time"))
            continue
        score_match = _SCENE_SCORE.search(line)
        if score_match and pending_time is not None:
            score = min(1.0, float(score_match.group("score")))
            cuts.append(SceneCut(time=pending_time, score=score))
            pending_time = None
    return sorted(cuts, key=lambda cut: cut.time)


def filter_scene_cuts(
    cuts: list[SceneCut],
    *,
    min_score: float,
    min_gap_seconds: float,
) -> list[float]:
    """Keep strong cuts; within `min_gap_seconds` only the strongest survives.

    FFmpeg scores the very first frame against nothing, so it always looks like a cut;
    a shot cannot be shorter than the minimum gap, which also rules that artefact out.
    """
    strong = [
        cut for cut in cuts if cut.score >= min_score and cut.time >= min_gap_seconds
    ]
    kept: list[SceneCut] = []
    for cut in strong:
        if kept and cut.time - kept[-1].time < min_gap_seconds:
            if cut.score > kept[-1].score:
                kept[-1] = cut
            continue
        kept.append(cut)
    return [cut.time for cut in kept]


def detect_scene_cuts(
    settings: Settings,
    source_path: Path,
    *,
    timeout_seconds: float,
) -> list[SceneCut]:
    command = build_scene_command(settings, source_path)
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        logger.warning("scene detection timed out")
        raise MediaProcessingError("Video analysis took too long. Try a shorter video.") from exc
    if completed.returncode != 0:
        tail = completed.stderr.strip().splitlines()
        logger.warning(
            "ffmpeg scene detection failed code=%s stderr_tail=%s",
            completed.returncode,
            tail[-3:],
        )
        raise MediaProcessingError("We couldn't analyze this video.")
    return parse_scene_metadata(completed.stdout)
