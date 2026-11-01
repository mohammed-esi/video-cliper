"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiRequestError } from "@/lib/api/errors";
import {
  buildPortraitStreamUrl,
  probePortraitStream,
  requestPortraitRender,
  waitForPortraitJob,
} from "@/lib/api/portrait";

const CONFLICT_RETRY_MS = 2000;
const MAX_CONFLICT_RETRIES = 30;

export type PortraitPreviewPhase =
  | "idle"
  | "checking"
  | "waiting"
  | "rendering"
  | "loading"
  | "ready"
  | "error";

export interface UseEditorPortraitPreviewResult {
  streamUrl: string | undefined;
  phase: PortraitPreviewPhase;
  renderProgress: number | undefined;
  statusLabel: string;
  errorMessage: string | null;
  retry: () => void;
  markPlaybackReady: () => void;
}

export interface UseEditorPortraitPreviewOptions {
  videoId: string;
  clipId: string | null;
  /** Saved-trim revision; must not change during live trim drags. */
  trimRevision: string | null;
  enabled: boolean;
}

function isStaleDiscarded(result: Record<string, unknown> | null): boolean {
  return result?.stale_discarded === true;
}

export function useEditorPortraitPreview(
  options: UseEditorPortraitPreviewOptions,
): UseEditorPortraitPreviewResult {
  const { videoId, clipId, trimRevision, enabled } = options;
  const inactive = !enabled || !clipId || !trimRevision;

  const [streamUrl, setStreamUrl] = useState<string | undefined>();
  const [phase, setPhase] = useState<PortraitPreviewPhase>("idle");
  const [renderProgress, setRenderProgress] = useState<number | undefined>();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [runToken, setRunToken] = useState(0);

  const generationRef = useRef(0);

  const retry = useCallback(() => {
    setErrorMessage(null);
    setRunToken((value) => value + 1);
  }, []);

  const markPlaybackReady = useCallback(() => {
    setPhase((current) => (current === "loading" ? "ready" : current));
  }, []);

  useEffect(() => {
    generationRef.current += 1;
    const generation = generationRef.current;

    if (inactive || !clipId || !trimRevision) {
      return;
    }

    const activeClipId = clipId;
    const activeRevision = trimRevision;

    let cancelled = false;
    let conflictTimer: ReturnType<typeof setTimeout> | undefined;
    const abortController = new AbortController();

    const isCurrent = () =>
      !cancelled && generation === generationRef.current;

    const clearConflictTimer = () => {
      if (conflictTimer) {
        clearTimeout(conflictTimer);
        conflictTimer = undefined;
      }
    };

    const setPortraitReady = () => {
      if (!isCurrent()) {
        return;
      }
      setStreamUrl(
        buildPortraitStreamUrl(videoId, activeClipId, activeRevision),
      );
      setPhase("loading");
      setRenderProgress(undefined);
      setErrorMessage(null);
    };

    const fail = (message: string) => {
      if (!isCurrent()) {
        return;
      }
      setStreamUrl(undefined);
      setPhase("error");
      setRenderProgress(undefined);
      setErrorMessage(message);
    };

    async function pollJob(jobId: string): Promise<boolean> {
      try {
        const job = await waitForPortraitJob(jobId, {
          signal: abortController.signal,
          onProgress: (progress) => {
            if (isCurrent()) {
              setRenderProgress(progress);
            }
          },
        });

        if (!isCurrent()) {
          return false;
        }

        if (job.status === "failed") {
          fail(
            job.error_message?.trim() ||
              "Portrait rendering failed. Please try again.",
          );
          return false;
        }

        if (isStaleDiscarded(job.result)) {
          fail(
            "This clip changed while rendering. Saving finished — try again.",
          );
          return false;
        }

        const probe = await probePortraitStream(
          videoId,
          activeClipId,
          activeRevision,
          abortController.signal,
        );
        if (!isCurrent()) {
          return false;
        }
        if (probe === "ready") {
          setPortraitReady();
          return true;
        }
        return false;
      } catch (error) {
        if (!isCurrent() || abortController.signal.aborted) {
          return false;
        }
        fail(
          error instanceof ApiRequestError
            ? error.message
            : "We couldn't finish portrait rendering. Please try again.",
        );
        return false;
      }
    }

    async function requestAndFollow(conflictAttempt = 0): Promise<void> {
      if (!isCurrent()) {
        return;
      }
      setPhase("rendering");
      setRenderProgress(undefined);
      setStreamUrl(undefined);

      try {
        const job = await requestPortraitRender(
          videoId,
          activeClipId,
          abortController.signal,
        );
        if (!isCurrent()) {
          return;
        }

        if (job.status === "completed") {
          if (isStaleDiscarded(job.result)) {
            fail(
              "This clip changed while rendering. Saving finished — try again.",
            );
            return;
          }
          setPortraitReady();
          return;
        }

        await pollJob(job.job_id);
      } catch (error) {
        if (!isCurrent() || abortController.signal.aborted) {
          return;
        }
        if (
          error instanceof ApiRequestError &&
          error.status === 409 &&
          conflictAttempt < MAX_CONFLICT_RETRIES
        ) {
          setPhase("waiting");
          setRenderProgress(undefined);
          clearConflictTimer();
          conflictTimer = setTimeout(() => {
            void requestAndFollow(conflictAttempt + 1);
          }, CONFLICT_RETRY_MS);
          return;
        }
        fail(
          error instanceof ApiRequestError
            ? error.message
            : "We couldn't start portrait rendering. Please try again.",
        );
      }
    }

    async function run(): Promise<void> {
      setPhase("checking");
      setRenderProgress(undefined);
      setStreamUrl(undefined);
      setErrorMessage(null);

      try {
        const probe = await probePortraitStream(
          videoId,
          activeClipId,
          activeRevision,
          abortController.signal,
        );
        if (!isCurrent()) {
          return;
        }

        if (probe === "ready") {
          setPortraitReady();
          return;
        }

        if (probe === "processing") {
          setPhase("waiting");
          await requestAndFollow(0);
          return;
        }

        await requestAndFollow(0);
      } catch (error) {
        if (!isCurrent() || abortController.signal.aborted) {
          return;
        }
        fail(
          error instanceof ApiRequestError
            ? error.message
            : "We couldn't load the portrait preview. Please try again.",
        );
      }
    }

    void run();

    return () => {
      cancelled = true;
      clearConflictTimer();
      abortController.abort();
    };
  }, [videoId, clipId, trimRevision, inactive, runToken]);

  const statusLabel = (() => {
    switch (phase) {
      case "checking":
        return "Checking portrait preview…";
      case "waiting":
        return "Waiting for other processing to finish…";
      case "rendering":
        return "Rendering portrait video…";
      case "loading":
        return "Loading portrait video…";
      case "ready":
        return "Portrait clip preview";
      case "error":
        return "Portrait preview unavailable";
      default:
        return "Select a clip to preview";
    }
  })();

  return {
    streamUrl: inactive ? undefined : streamUrl,
    phase: inactive ? "idle" : phase,
    renderProgress: inactive ? undefined : renderProgress,
    statusLabel: inactive ? "Select a clip to preview" : statusLabel,
    errorMessage: inactive ? null : errorMessage,
    retry,
    markPlaybackReady,
  };
}
