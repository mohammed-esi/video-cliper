import { apiJson } from "./request";
import type { JobOperation, JobResponse, JobStatus } from "./types";

function isJobStatus(value: unknown): value is JobStatus {
  return (
    value === "queued" ||
    value === "processing" ||
    value === "completed" ||
    value === "failed"
  );
}

function isJobOperation(value: unknown): value is JobOperation {
  return (
    value === "lifecycle_test" ||
    value === "generate_clips" ||
    value === "render_portrait_clip" ||
    value === "batch_export_clips"
  );
}

export function isJobResponse(value: unknown): value is JobResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const job = value as JobResponse;
  return (
    typeof job.job_id === "string" &&
    typeof job.video_id === "string" &&
    isJobOperation(job.operation) &&
    isJobStatus(job.status) &&
    typeof job.progress === "number" &&
    typeof job.created_at === "string" &&
    typeof job.updated_at === "string" &&
    (job.error_message === null || typeof job.error_message === "string") &&
    (job.result === null || typeof job.result === "object")
  );
}

export interface CreateJobRequest {
  video_id: string;
  operation: JobOperation;
}

export async function createJob(
  body: CreateJobRequest,
  signal?: AbortSignal,
): Promise<JobResponse> {
  return apiJson(
    "/api/jobs",
    {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    isJobResponse,
    "We couldn't start processing. Please try again.",
  );
}

export function createGenerateClipsJob(
  videoId: string,
  signal?: AbortSignal,
): Promise<JobResponse> {
  return createJob({ video_id: videoId, operation: "generate_clips" }, signal);
}

export async function getJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<JobResponse> {
  return apiJson(
    `/api/jobs/${encodeURIComponent(jobId)}`,
    { method: "GET", signal },
    isJobResponse,
    "We couldn't load processing status. Please try again.",
  );
}
