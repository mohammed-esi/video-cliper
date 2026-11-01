"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  buildBatchExportDownloadUrl,
  mapBatchExportJobProgress,
  startBatchExportJob,
  type BatchExportClipPayload,
  type BatchExportProgressView,
} from "@/lib/api/batch-export";
import { ApiRequestError } from "@/lib/api/errors";
import { triggerPortraitDownload } from "@/lib/clips/clip-export";

import { useJobPolling } from "../processing/useJobPolling";

export type BatchExportUiState =
  | { status: "idle" }
  | { status: "running"; progress: BatchExportProgressView; jobId: string }
  | { status: "failed"; message: string; jobId?: string }
  | { status: "completed"; jobId: string };

export interface UseBatchClipExportOptions {
  videoId: string;
}

export interface UseBatchClipExportResult {
  state: BatchExportUiState;
  startExport: (clips: BatchExportClipPayload[]) => void;
  retry: () => void;
}

function deriveBatchState(input: {
  jobId: string | null;
  completedJobId: string | null;
  job: ReturnType<typeof useJobPolling>["job"];
  pollingError: string | null;
  startError: string | null;
  pendingTotal: number;
}): BatchExportUiState {
  if (input.startError) {
    return { status: "failed", message: input.startError };
  }
  if (input.completedJobId) {
    return { status: "completed", jobId: input.completedJobId };
  }
  if (input.pollingError && input.jobId) {
    return { status: "failed", message: input.pollingError, jobId: input.jobId };
  }
  if (!input.jobId) {
    return { status: "idle" };
  }
  if (!input.job) {
    return {
      status: "running",
      jobId: input.jobId,
      progress: {
        phase: "queued",
        label: "Preparing export…",
        currentIndex: 0,
        total: input.pendingTotal,
      },
    };
  }
  if (input.job.status === "failed") {
    return {
      status: "failed",
      message:
        input.job.error_message ??
        "We couldn't finish the export. Please try again.",
      jobId: input.job.job_id,
    };
  }
  if (input.job.status === "completed") {
    return { status: "completed", jobId: input.job.job_id };
  }
  return {
    status: "running",
    jobId: input.job.job_id,
    progress: mapBatchExportJobProgress(input.job),
  };
}

export function useBatchClipExport(
  options: UseBatchClipExportOptions,
): UseBatchClipExportResult {
  const { videoId } = options;
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [completedJobId, setCompletedJobId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [pendingTotal, setPendingTotal] = useState(0);
  const lastPayloadRef = useRef<BatchExportClipPayload[] | null>(null);
  const downloadedJobRef = useRef<string | null>(null);

  const { job, pollingError } = useJobPolling(activeJobId);

  const state = useMemo(
    () =>
      deriveBatchState({
        jobId: activeJobId,
        completedJobId,
        job,
        pollingError,
        startError,
        pendingTotal,
      }),
    [activeJobId, completedJobId, job, pollingError, startError, pendingTotal],
  );

  useEffect(() => {
    if (state.status !== "completed") {
      return;
    }
    if (downloadedJobRef.current === state.jobId) {
      return;
    }
    downloadedJobRef.current = state.jobId;
    triggerPortraitDownload(buildBatchExportDownloadUrl(videoId, state.jobId));
  }, [state, videoId]);

  useEffect(() => {
    if (job?.status !== "completed") {
      return;
    }
    const task = window.setTimeout(() => {
      setCompletedJobId(job.job_id);
      setActiveJobId(null);
    }, 0);
    return () => window.clearTimeout(task);
  }, [job]);

  const startExport = useCallback(
    (clips: BatchExportClipPayload[]) => {
      if (clips.length === 0 || activeJobId !== null) {
        return;
      }
      lastPayloadRef.current = clips;
      setStartError(null);
      setCompletedJobId(null);
      setPendingTotal(clips.length);
      downloadedJobRef.current = null;

      void (async () => {
        try {
          const created = await startBatchExportJob(videoId, { clips });
          setActiveJobId(created.job_id);
        } catch (error) {
          const message =
            error instanceof ApiRequestError
              ? error.message
              : "We couldn't start the export. Please try again.";
          setStartError(message);
        }
      })();
    },
    [activeJobId, videoId],
  );

  const retry = useCallback(() => {
    const payload = lastPayloadRef.current;
    if (!payload || payload.length === 0) {
      return;
    }
    setStartError(null);
    startExport(payload);
  }, [startExport]);

  return { state, startExport, retry };
}
