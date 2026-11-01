import type { JobResponse, JobStatus } from "@/lib/api/types";
import type { JobStage } from "@/features/processing/JobProgress";

export type ProcessingSource = "upload" | "youtube";

export interface JobProgressViewModel {
  stage: JobStage;
  progress?: number;
  message?: string;
  error?: string | null;
  isTerminal: boolean;
}

export function isProcessingSource(value: string): value is ProcessingSource {
  return value === "upload" || value === "youtube";
}

export function jobStatusMessage(status: JobStatus): string | undefined {
  switch (status) {
    case "queued":
      return "Waiting in the queue…";
    case "processing":
      return "Creating clip previews…";
    case "completed":
    case "failed":
      return undefined;
  }
}

/** Maps backend job status to the existing JobProgress presentation model. */
export function mapJobToProgressView(job: JobResponse): JobProgressViewModel {
  if (job.status === "failed") {
    return {
      stage: "processing",
      error:
        job.error_message?.trim() ||
        "We couldn't finish preparing your clips. Please try again.",
      isTerminal: true,
    };
  }

  if (job.status === "completed") {
    return {
      stage: "completed",
      progress: 1,
      isTerminal: true,
    };
  }

  return {
    stage: "processing",
    progress: job.status === "processing" ? job.progress : undefined,
    message: jobStatusMessage(job.status),
    isTerminal: false,
  };
}
