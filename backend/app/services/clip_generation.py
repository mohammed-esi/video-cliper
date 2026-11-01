import logging
import uuid
from pathlib import Path

from app.core.config import Settings
from app.core.errors import MediaProcessingError
from app.schemas.clip import ClipMetadata
from app.services.clip_storage import (
    clips_directory,
    commit_clips_manifest,
    remove_clip_files,
)
from app.services.disk_space import ensure_disk_space_for_bytes
from app.services.ffmpeg_runner import ffmpeg_input_argument, run_ffmpeg
from app.services.ffprobe import run_ffprobe
from app.services.job_context import JobExecutionContext
from app.services.job_operations import ProgressCallback
from app.services.processing_worker import is_shutdown_requested
from app.services.segmentation import compute_time_segments
from app.services.video_storage import find_source_video_path

logger = logging.getLogger(__name__)


def _build_ffmpeg_command(
    settings: Settings,
    *,
    source_path: Path,
    output_path: Path,
    start_time: float,
    duration: float,
    has_audio: bool,
) -> list[str]:
    command = [
        settings.ffmpeg_path,
        "-nostdin",
        "-y",
        "-protocol_whitelist",
        "file,pipe",
        "-ss",
        f"{start_time:.6f}",
        "-t",
        f"{duration:.6f}",
        "-i",
        ffmpeg_input_argument(source_path),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "veryfast",
        "-crf",
        "20",
    ]
    if has_audio:
        command.extend(["-c:a", "aac", "-b:a", "128k"])
    else:
        command.append("-an")
    command.extend(["-movflags", "+faststart", str(output_path)])
    return command


def _estimate_required_bytes(source_size: int, clip_count: int) -> int:
    # Conservative: each re-encoded clip may approach source size in worst case.
    return max(source_size, 1) * max(clip_count, 1)


def run_generate_clips(update_progress: ProgressCallback, context: JobExecutionContext) -> dict:
    settings = context.settings
    video_id = context.video_id
    source_path = find_source_video_path(settings, video_id)
    source_probe = run_ffprobe(source_path, settings)

    segments = compute_time_segments(
        source_probe.duration_seconds,
        target_length=settings.clip_target_duration_seconds,
        min_tail_to_merge=settings.clip_min_tail_merge_seconds,
        min_clip_duration=settings.clip_min_duration_seconds,
    )
    if not segments:
        raise MediaProcessingError("This video is too short to generate clips.")

    output_dir = clips_directory(settings, video_id)
    source_size = source_path.stat().st_size
    ensure_disk_space_for_bytes(
        settings,
        output_dir,
        _estimate_required_bytes(source_size, len(segments)),
    )

    generated: list[ClipMetadata] = []
    new_outputs: list[Path] = []
    total = len(segments)

    try:
        for index, (start_time, end_time) in enumerate(segments):
            if is_shutdown_requested():
                raise MediaProcessingError("Video processing was interrupted.")

            duration = end_time - start_time
            clip_id = uuid.uuid4()
            output_path = output_dir / f"{clip_id}.mp4"
            command = _build_ffmpeg_command(
                settings,
                source_path=source_path,
                output_path=output_path,
                start_time=start_time,
                duration=duration,
                has_audio=source_probe.has_audio,
            )
            run_ffmpeg(
                command,
                timeout_seconds=settings.ffmpeg_clip_timeout_seconds,
                cancelled=None,
            )
            if not output_path.is_file() or output_path.stat().st_size == 0:
                raise MediaProcessingError("Generated clip file is invalid.")

            clip_probe = run_ffprobe(output_path, settings)
            new_outputs.append(output_path.resolve())
            generated.append(
                ClipMetadata(
                    clip_id=clip_id,
                    video_id=video_id,
                    start_time=start_time,
                    end_time=end_time,
                    duration=end_time - start_time,
                    generated_start_time=start_time,
                    generated_end_time=end_time,
                    storage_name=f"clips/{clip_id}.mp4",
                    width=clip_probe.width,
                    height=clip_probe.height,
                    has_audio=clip_probe.has_audio,
                )
            )
            update_progress((index + 1) / total)
    except Exception:
        remove_clip_files(new_outputs)
        raise

    try:
        commit_clips_manifest(settings, video_id, generated, set(new_outputs))
    except Exception:
        remove_clip_files(new_outputs)
        raise
    logger.info(
        "Generated clips video_id=%s count=%s job_id=%s",
        video_id,
        len(generated),
        context.job_id,
    )
    return {
        "operation": "generate_clips",
        "clip_count": len(generated),
        "clips": [clip.model_dump(mode="json") for clip in generated],
    }
