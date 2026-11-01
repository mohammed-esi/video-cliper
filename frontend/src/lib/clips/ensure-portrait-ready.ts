import { ApiRequestError } from "@/lib/api/errors";
import {
  probePortraitStream,
  requestPortraitRender,
  waitForPortraitJob,
} from "@/lib/api/portrait";

const CONFLICT_RETRY_MS = 2000;
const MAX_CONFLICT_RETRIES = 30;

function isStaleDiscarded(result: Record<string, unknown> | null): boolean {
  return result?.stale_discarded === true;
}

export type EnsurePortraitPhase =
  | "checking"
  | "waiting"
  | "rendering";

export interface EnsurePortraitReadyOptions {
  videoId: string;
  clipId: string;
  trimRevision: string;
  signal?: AbortSignal;
  onPhase?: (phase: EnsurePortraitPhase) => void;
}

export async function ensurePortraitReady(
  options: EnsurePortraitReadyOptions,
): Promise<void> {
  const { videoId, clipId, trimRevision, signal, onPhase } = options;

  onPhase?.("checking");
  const initial = await probePortraitStream(
    videoId,
    clipId,
    trimRevision,
    signal,
  );
  if (initial === "ready") {
    return;
  }

  if (initial === "processing") {
    onPhase?.("waiting");
    await requestAndFollow(videoId, clipId, trimRevision, signal, onPhase, 0);
    return;
  }

  await requestAndFollow(videoId, clipId, trimRevision, signal, onPhase, 0);
}

async function requestAndFollow(
  videoId: string,
  clipId: string,
  trimRevision: string,
  signal: AbortSignal | undefined,
  onPhase: EnsurePortraitReadyOptions["onPhase"],
  conflictAttempt: number,
): Promise<void> {
  onPhase?.("rendering");
  try {
    const job = await requestPortraitRender(videoId, clipId, signal);
    if (job.status === "completed") {
      if (isStaleDiscarded(job.result)) {
        throw new ApiRequestError(
          "This clip changed while rendering. Please try exporting again.",
        );
      }
      await assertPortraitProbeReady(videoId, clipId, trimRevision, signal);
      return;
    }
    await pollPortraitJob(job.job_id, videoId, clipId, trimRevision, signal);
  } catch (error) {
    if (
      error instanceof ApiRequestError &&
      error.status === 409 &&
      conflictAttempt < MAX_CONFLICT_RETRIES
    ) {
      onPhase?.("waiting");
      await sleep(CONFLICT_RETRY_MS, signal);
      await requestAndFollow(
        videoId,
        clipId,
        trimRevision,
        signal,
        onPhase,
        conflictAttempt + 1,
      );
      return;
    }
    throw error;
  }
}

async function pollPortraitJob(
  jobId: string,
  videoId: string,
  clipId: string,
  trimRevision: string,
  signal: AbortSignal | undefined,
): Promise<void> {
  const job = await waitForPortraitJob(jobId, { signal });
  if (job.status === "failed") {
    throw new ApiRequestError(
      job.error_message?.trim() ||
        "Portrait rendering failed. Please try again.",
    );
  }
  if (isStaleDiscarded(job.result)) {
    throw new ApiRequestError(
      "This clip changed while rendering. Please try exporting again.",
    );
  }
  await assertPortraitProbeReady(videoId, clipId, trimRevision, signal);
}

async function assertPortraitProbeReady(
  videoId: string,
  clipId: string,
  trimRevision: string,
  signal: AbortSignal | undefined,
): Promise<void> {
  const probe = await probePortraitStream(
    videoId,
    clipId,
    trimRevision,
    signal,
  );
  if (probe !== "ready") {
    throw new ApiRequestError(
      "The portrait file is not ready yet. Please try again.",
    );
  }
}

function sleep(ms: number, signal: AbortSignal | undefined): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new ApiRequestError("Export was cancelled."));
      return;
    }
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new ApiRequestError("Export was cancelled."));
      },
      { once: true },
    );
  });
}
