import {
  buildPortraitDownloadPath,
  buildPortraitStreamPath,
} from "@/lib/clips/portrait-stream-url";

import { getApiBaseUrl } from "./config";
import { ApiRequestError } from "./errors";
import { getJob } from "./jobs";
import { apiJson } from "./request";
import type { JobResponse } from "./types";

function isJobResponse(value: unknown): value is JobResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const job = value as JobResponse;
  return (
    typeof job.job_id === "string" &&
    typeof job.video_id === "string" &&
    typeof job.operation === "string" &&
    typeof job.status === "string" &&
    typeof job.progress === "number"
  );
}

export function buildPortraitStreamUrl(
  videoId: string,
  clipId: string,
  revision: string,
): string {
  return `${getApiBaseUrl()}${buildPortraitStreamPath(videoId, clipId, revision)}`;
}

export function buildPortraitDownloadUrl(
  videoId: string,
  clipId: string,
  revision: string,
): string {
  return `${getApiBaseUrl()}${buildPortraitDownloadPath(videoId, clipId, revision)}`;
}

export type PortraitStreamProbe = "ready" | "missing" | "processing";

/** Lightweight check whether the current portrait MP4 exists for this trim revision. */
export async function probePortraitStream(
  videoId: string,
  clipId: string,
  revision: string,
  signal?: AbortSignal,
): Promise<PortraitStreamProbe> {
  const response = await fetch(
    buildPortraitStreamUrl(videoId, clipId, revision),
    {
      method: "GET",
      cache: "no-store",
      signal,
      headers: { Range: "bytes=0-0" },
    },
  );

  if (response.status === 200 || response.status === 206) {
    return "ready";
  }
  if (response.status === 404) {
    return "missing";
  }
  if (response.status === 409) {
    return "processing";
  }

  const message =
    response.status === 415
      ? "This clip's source video couldn't be used for portrait rendering."
      : "We couldn't check the portrait preview. Please try again.";
  throw new ApiRequestError(message, response.status);
}

export async function requestPortraitRender(
  videoId: string,
  clipId: string,
  signal?: AbortSignal,
): Promise<JobResponse> {
  return apiJson(
    `/api/videos/${encodeURIComponent(videoId)}/clips/${encodeURIComponent(clipId)}/portrait`,
    { method: "POST", signal },
    isJobResponse,
    "We couldn't start portrait rendering. Please try again.",
  );
}

const PORTRAIT_POLL_INTERVAL_MS = 1500;

export async function waitForPortraitJob(
  jobId: string,
  options: {
    signal?: AbortSignal;
    onProgress?: (progress: number, status: JobResponse["status"]) => void;
  } = {},
): Promise<JobResponse> {
  while (true) {
    if (options.signal?.aborted) {
      throw new ApiRequestError("Portrait rendering was cancelled.");
    }

    const job = await getJob(jobId, options.signal);
    options.onProgress?.(job.progress, job.status);

    if (job.status === "completed" || job.status === "failed") {
      return job;
    }

    await new Promise<void>((resolve, reject) => {
      if (options.signal?.aborted) {
        reject(new ApiRequestError("Portrait rendering was cancelled."));
        return;
      }
      const timer = setTimeout(resolve, PORTRAIT_POLL_INTERVAL_MS);
      options.signal?.addEventListener(
        "abort",
        () => {
          clearTimeout(timer);
          reject(new ApiRequestError("Portrait rendering was cancelled."));
        },
        { once: true },
      );
    });
  }
}
