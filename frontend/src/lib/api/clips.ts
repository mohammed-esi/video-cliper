import { apiJson } from "./request";
import type { ClipListResponse, ClipMetadata } from "./types";

function isClipMetadata(value: unknown): value is ClipMetadata {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const clip = value as ClipMetadata;
  return (
    typeof clip.clip_id === "string" &&
    typeof clip.video_id === "string" &&
    typeof clip.start_time === "number" &&
    typeof clip.end_time === "number" &&
    typeof clip.duration === "number" &&
    typeof clip.generated_start_time === "number" &&
    typeof clip.generated_end_time === "number" &&
    typeof clip.storage_name === "string" &&
    typeof clip.width === "number" &&
    typeof clip.height === "number" &&
    typeof clip.has_audio === "boolean"
  );
}

function isClipListResponse(value: unknown): value is ClipListResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const list = value as ClipListResponse;
  return (
    typeof list.video_id === "string" &&
    typeof list.source_duration_seconds === "number" &&
    Array.isArray(list.clips) &&
    list.clips.every(isClipMetadata)
  );
}

export async function listVideoClips(
  videoId: string,
  signal?: AbortSignal,
): Promise<ClipListResponse> {
  return apiJson(
    `/api/videos/${encodeURIComponent(videoId)}/clips`,
    { method: "GET", signal },
    isClipListResponse,
    "We couldn't load your clips. Please try again.",
  );
}

export async function updateClipTrim(
  videoId: string,
  clipId: string,
  range: { start_time: number; end_time: number },
  signal?: AbortSignal,
): Promise<ClipMetadata> {
  return apiJson(
    `/api/videos/${encodeURIComponent(videoId)}/clips/${encodeURIComponent(clipId)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(range),
      signal,
    },
    isClipMetadata,
    "We couldn't save your trim changes. Please try again.",
  );
}
