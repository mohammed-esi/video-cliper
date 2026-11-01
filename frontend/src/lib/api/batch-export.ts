import { getApiBaseUrl } from "./config";
import { isJobResponse } from "./jobs";
import { apiJson } from "./request";
import type { JobResponse } from "./types";

export interface BatchExportClipPayload {
  clip_id: string;
  trim_revision: string;
}

export interface BatchExportRequestBody {
  clips: BatchExportClipPayload[];
}

export async function startBatchExportJob(
  videoId: string,
  body: BatchExportRequestBody,
  signal?: AbortSignal,
): Promise<JobResponse> {
  return apiJson<JobResponse>(
    `/api/videos/${encodeURIComponent(videoId)}/exports/batch`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    },
    isJobResponse,
    "We couldn't start the export. Please try again.",
  );
}

export function buildBatchExportDownloadUrl(
  videoId: string,
  jobId: string,
): string {
  const base = getApiBaseUrl();
  const path = `/api/videos/${encodeURIComponent(videoId)}/exports/batch/${encodeURIComponent(jobId)}/download`;
  return base ? `${base}${path}` : path;
}

export interface BatchExportProgressView {
  phase: "idle" | "queued" | "rendering" | "packaging" | "completed" | "failed";
  label: string;
  currentIndex: number;
  total: number;
}

export function mapBatchExportJobProgress(
  job: JobResponse,
): BatchExportProgressView {
  const result = job.result ?? {};
  const total =
    typeof result.total === "number" && result.total > 0
      ? result.total
      : typeof result.clip_count === "number"
        ? result.clip_count
        : 0;
  const currentIndex =
    typeof result.current_index === "number" ? result.current_index : 0;
  const phaseRaw = typeof result.phase === "string" ? result.phase : "";

  if (job.status === "failed") {
    return {
      phase: "failed",
      label: job.error_message ?? "Export failed.",
      currentIndex,
      total,
    };
  }

  if (job.status === "completed") {
    return {
      phase: "completed",
      label: "Export ready",
      currentIndex: total || currentIndex,
      total: total || currentIndex,
    };
  }

  if (phaseRaw === "packaging") {
    return {
      phase: "packaging",
      label: "Packaging ZIP…",
      currentIndex,
      total,
    };
  }

  if (job.status === "queued" || phaseRaw === "queued") {
    return {
      phase: "queued",
      label: "Preparing export…",
      currentIndex: 0,
      total,
    };
  }

  if (total > 0 && currentIndex > 0) {
    return {
      phase: "rendering",
      label: `Processing clip ${currentIndex} of ${total}`,
      currentIndex,
      total,
    };
  }

  return {
    phase: "rendering",
    label: "Preparing export…",
    currentIndex,
    total,
  };
}
