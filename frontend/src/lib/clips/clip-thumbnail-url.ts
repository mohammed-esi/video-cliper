/** Cache-busting token tied to saved trim boundaries (not live drag state). */
export function clipThumbnailRevision(
  startTime: number,
  endTime: number,
): string {
  return `${startTime.toFixed(1)}_${endTime.toFixed(1)}`;
}

export function buildClipThumbnailPath(
  videoId: string,
  clipId: string,
  revision: string,
): string {
  const params = new URLSearchParams({ v: revision });
  return `/api/videos/${encodeURIComponent(videoId)}/clips/${encodeURIComponent(clipId)}/thumbnail?${params.toString()}`;
}
