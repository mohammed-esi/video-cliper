"""Trim revision tokens shared with the frontend (`clipThumbnailRevision`)."""


def clip_trim_revision(start_time: float, end_time: float) -> str:
    return f"{start_time:.1f}_{end_time:.1f}"
