import pytest

from app.core.errors import InvalidInputError
from app.services.youtube_urls import parse_youtube_url


def test_parse_watch_url() -> None:
    parsed = parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert parsed.video_id == "dQw4w9WgXcQ"
    assert parsed.canonical_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_parse_youtu_be_url() -> None:
    parsed = parse_youtube_url("https://youtu.be/dQw4w9WgXcQ")
    assert parsed.video_id == "dQw4w9WgXcQ"


def test_parse_shorts_url() -> None:
    parsed = parse_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ")
    assert parsed.video_id == "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://evil.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/playlist?list=PL123",
        "https://127.0.0.1/watch?v=dQw4w9WgXcQ",
    ],
)
def test_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(InvalidInputError):
        parse_youtube_url(url)
