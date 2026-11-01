import { buildClipThumbnailPath } from "@/lib/clips/clip-thumbnail-url";

import { getApiBaseUrl } from "./config";

export { clipThumbnailRevision } from "@/lib/clips/clip-thumbnail-url";

export function buildClipThumbnailUrl(
  videoId: string,
  clipId: string,
  revision: string,
): string {
  return `${getApiBaseUrl()}${buildClipThumbnailPath(videoId, clipId, revision)}`;
}
