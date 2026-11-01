import re
from dataclasses import dataclass

from app.core.errors import InvalidInputError

_ALLOWED_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
    },
)
_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


@dataclass(frozen=True, slots=True)
class ParsedYoutubeUrl:
    video_id: str
    canonical_url: str


def parse_youtube_url(raw: str) -> ParsedYoutubeUrl:
    trimmed = raw.strip()
    if not trimmed:
        raise InvalidInputError("Paste a YouTube link to continue.")

    if not trimmed.startswith("https://"):
        raise InvalidInputError("Use a secure https:// YouTube link.")

    try:
        from urllib.parse import urlparse

        parsed = urlparse(trimmed)
    except ValueError as exc:
        raise InvalidInputError("This doesn't look like a valid YouTube link.") from exc

    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or hostname not in _ALLOWED_HOSTS:
        raise InvalidInputError("Use a link from youtube.com or youtu.be.")

    if parsed.username or parsed.password or parsed.port:
        raise InvalidInputError("This link doesn't point to a single YouTube video.")

    path_parts = [part for part in parsed.path.split("/") if part]
    video_id: str | None = None

    if hostname == "youtu.be":
        if len(path_parts) != 1:
            raise InvalidInputError("This link doesn't point to a single YouTube video.")
        video_id = path_parts[0]
    elif parsed.path == "/watch":
        from urllib.parse import parse_qs

        query = parse_qs(parsed.query)
        candidates = query.get("v", [])
        if len(candidates) != 1:
            raise InvalidInputError("This link doesn't point to a single YouTube video.")
        video_id = candidates[0]
    elif len(path_parts) >= 2 and path_parts[0] in {"embed", "live", "shorts"}:
        video_id = path_parts[1]
    else:
        raise InvalidInputError("This link doesn't point to a single YouTube video.")

    if not video_id or not _VIDEO_ID_PATTERN.fullmatch(video_id):
        raise InvalidInputError("This link doesn't point to a single YouTube video.")

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    return ParsedYoutubeUrl(video_id=video_id, canonical_url=canonical_url)
