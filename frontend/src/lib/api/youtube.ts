import {
  ApiRequestError,
  UploadAbortError,
  parseApiErrorBody,
} from "./errors";
import { getApiBaseUrl } from "./config";
import type { VideoUploadResponse } from "./types";

function isVideoUploadResponse(value: unknown): value is VideoUploadResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "video_id" in value &&
    typeof (value as VideoUploadResponse).video_id === "string" &&
    "duration_seconds" in value &&
    typeof (value as VideoUploadResponse).duration_seconds === "number"
  );
}

export interface ImportYoutubeOptions {
  signal?: AbortSignal;
}

/**
 * Imports a YouTube video. Aborting only cancels the browser request; the
 * server may continue downloading until its timeout or completion.
 */
export async function importYoutubeVideo(
  url: string,
  options: ImportYoutubeOptions = {},
): Promise<VideoUploadResponse> {
  if (options.signal?.aborted) {
    throw new UploadAbortError();
  }

  const response = await fetch(`${getApiBaseUrl()}/api/videos/youtube`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
    signal: options.signal,
    cache: "no-store",
  });

  const body: unknown = await response.json().catch(() => null);

  if (response.ok) {
    if (!isVideoUploadResponse(body)) {
      throw new ApiRequestError("Unexpected response from the server.");
    }
    return body;
  }

  const message =
    parseApiErrorBody(body) ??
    "We couldn't import this YouTube video. Try another link.";
  throw new ApiRequestError(message, response.status);
}
