from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import InvalidInputError, UnsupportedMediaError
from app.core.config import Settings
from app.services.ffprobe import (
    enforce_probe_limits,
    ffprobe_input_argument,
    parse_ffprobe_payload,
    run_ffprobe,
)


def test_parse_ffprobe_payload_landscape_video() -> None:
    payload = {
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "12.5"},
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "duration": "12.5",
            },
            {"codec_type": "audio"},
        ],
    }

    result = parse_ffprobe_payload(payload)

    assert result.duration_seconds == 12.5
    assert result.width == 1920
    assert result.height == 1080
    assert result.has_audio is True
    assert result.container == "mp4"


def test_parse_ffprobe_payload_portrait_dimensions_with_rotation() -> None:
    payload = {
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "3.0"},
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "tags": {"rotate": "90"},
            }
        ],
    }

    result = parse_ffprobe_payload(payload)

    assert result.width == 1080
    assert result.height == 1920


def test_parse_ffprobe_payload_rejects_hls() -> None:
    payload = {
        "format": {"format_name": "hls", "duration": "3.0"},
        "streams": [{"codec_type": "video", "width": 640, "height": 360}],
    }

    with pytest.raises(UnsupportedMediaError):
        parse_ffprobe_payload(payload)


def test_ffprobe_input_argument_uses_file_prefix(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00")

    assert ffprobe_input_argument(video).startswith("file:")
    assert "clip.mp4" in ffprobe_input_argument(video)


def test_run_ffprobe_passes_protocol_whitelist(tmp_path: Path) -> None:
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00")
    settings = Settings()

    completed = MagicMock(returncode=0, stdout='{"format": {"format_name": "mp4", "duration": "1"}, "streams": [{"codec_type": "video", "width": 640, "height": 360}]}')

    with patch("app.services.ffprobe.subprocess.run", return_value=completed) as run_mock:
        result = run_ffprobe(video, settings)

    assert result.width == 640
    command = run_mock.call_args.args[0]
    assert "-protocol_whitelist" in command
    assert "file,pipe" in command
    assert command[-2] == "-i"
    assert run_mock.call_args.kwargs.get("stdin") is not None
    assert str(command[-1]).startswith("file:")


def test_enforce_probe_limits_rejects_long_duration() -> None:
    from app.services.ffprobe import ProbeResult

    settings = Settings(max_duration_seconds=10)
    probe = ProbeResult(
        duration_seconds=11,
        width=640,
        height=360,
        has_audio=False,
        container="mp4",
    )

    with pytest.raises(InvalidInputError):
        enforce_probe_limits(probe, settings)
