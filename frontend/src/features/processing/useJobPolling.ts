"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getJob } from "@/lib/api/jobs";
import { ApiRequestError } from "@/lib/api/errors";
import type { JobResponse } from "@/lib/api/types";
import {
  mapJobToProgressView,
  type JobProgressViewModel,
} from "@/lib/processing/job-view-model";

const POLL_INTERVAL_MS = 1500;
const TRANSIENT_FAILURE_THRESHOLD = 3;

export interface UseJobPollingResult {
  job: JobResponse | null;
  view: JobProgressViewModel | null;
  isLoading: boolean;
  /** Set when polling stops due to repeated network errors. */
  pollingError: string | null;
  refresh: () => void;
}

export function useJobPolling(jobId: string | null): UseJobPollingResult {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [view, setView] = useState<JobProgressViewModel | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(jobId));
  const [pollingError, setPollingError] = useState<string | null>(null);
  const [pollGeneration, setPollGeneration] = useState(0);

  const inFlightRef = useRef(false);
  const transientFailuresRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  const refresh = useCallback(() => {
    transientFailuresRef.current = 0;
    setPollingError(null);
    setPollGeneration((value) => value + 1);
  }, []);

  useEffect(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    inFlightRef.current = false;
    transientFailuresRef.current = 0;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const schedule = (delayMs: number) => {
      timer = setTimeout(() => {
        void pollOnce();
      }, delayMs);
    };

    async function pollOnce() {
      if (cancelled || inFlightRef.current) {
        return;
      }

      inFlightRef.current = true;
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const nextJob = await getJob(jobId!, controller.signal);
        if (cancelled) {
          return;
        }

        transientFailuresRef.current = 0;
        setPollingError(null);
        setJob(nextJob);
        setView(mapJobToProgressView(nextJob));
        setIsLoading(false);

        if (nextJob.status === "completed" || nextJob.status === "failed") {
          return;
        }

        schedule(POLL_INTERVAL_MS);
      } catch (error) {
        if (cancelled || controller.signal.aborted) {
          return;
        }

        if (error instanceof ApiRequestError && error.status === 404) {
          setPollingError(
            error.message ||
              "This processing job could not be found. Start over from import.",
          );
          setIsLoading(false);
          return;
        }

        transientFailuresRef.current += 1;
        if (transientFailuresRef.current >= TRANSIENT_FAILURE_THRESHOLD) {
          setPollingError(
            "We couldn't reach the server. Check that the backend is running, then try again.",
          );
          setIsLoading(false);
          return;
        }

        schedule(POLL_INTERVAL_MS);
      } finally {
        inFlightRef.current = false;
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      }
    }

    void (async () => {
      if (!jobId) {
        setJob(null);
        setView(null);
        setIsLoading(false);
        setPollingError(null);
        return;
      }

      setIsLoading(true);
      await pollOnce();
    })();

    return () => {
      cancelled = true;
      if (timer) {
        clearTimeout(timer);
      }
      abortRef.current?.abort();
      abortRef.current = null;
      inFlightRef.current = false;
    };
  }, [jobId, pollGeneration]);

  return { job, view, isLoading, pollingError, refresh };
}
