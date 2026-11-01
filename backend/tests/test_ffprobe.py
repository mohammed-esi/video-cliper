import pytest

from app.core.errors import InvalidInputError, UnsupportedMediaError
from app.services.ffprobe import enforce_probe_limits, parse_ffprobe_payload


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


def test_enforce_probe_limits_rejects_long_duration() -> None:
    from app.core.config import Settings
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
