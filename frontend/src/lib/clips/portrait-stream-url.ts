import { clipThumbnailRevision } from "./clip-thumbnail-url";

/** Cache-busting query tied to saved trim (same revision as thumbnails). */
export { clipThumbnailRevision as portraitStreamRevision };

export function buildPortraitStreamPath(
  videoId: string,
  clipId: string,
  revision: string,
): string {
  const params = new URLSearchParams({ v: revision });
  return `/api/videos/${encodeURIComponent(videoId)}/clips/${encodeURIComponent(clipId)}/portrait?${params.toString()}`;
}

export function buildPortraitDownloadPath(
  videoId: string,
  clipId: string,
  revision: string,
): string {
  const params = new URLSearchParams({ v: revision });
  return `/api/videos/${encodeURIComponent(videoId)}/clips/${encodeURIComponent(clipId)}/portrait/download?${params.toString()}`;
}
