import {
  parsePendingJobHandoff,
  type PendingJobHandoff,
} from "./pending-job-handoff";

export type { PendingJobHandoff } from "./pending-job-handoff";
export { parsePendingJobHandoff } from "./pending-job-handoff";

const KEY = (videoId: string) => `video-clipper:pending-job:${videoId}`;

function readRaw(videoId: string): string | null {
  if (typeof sessionStorage === "undefined") {
    return null;
  }
  try {
    return sessionStorage.getItem(KEY(videoId));
  } catch {
    return null;
  }
}

/** Returns an in-flight start marker or a job ID already created for this video. */
export function readPendingJobHandoff(
  videoId: string,
): PendingJobHandoff | null {
  return parsePendingJobHandoff(readRaw(videoId));
}

/** Returns a job ID already created for this import, if any. */
export function readPendingJobId(videoId: string): string | null {
  const handoff = readPendingJobHandoff(videoId);
  if (handoff && handoff !== "starting") {
    return handoff.jobId;
  }
  return null;
}

export function markPendingJobStarting(videoId: string): void {
  if (typeof sessionStorage === "undefined") {
    return;
  }
  try {
    sessionStorage.setItem(KEY(videoId), "starting");
  } catch {
    // Ignore.
  }
}

export function savePendingJobId(videoId: string, jobId: string): void {
  if (typeof sessionStorage === "undefined") {
    return;
  }
  try {
    sessionStorage.setItem(KEY(videoId), jobId);
  } catch {
    // Ignore.
  }
}

export function clearPendingJobId(videoId: string): void {
  if (typeof sessionStorage === "undefined") {
    return;
  }
  try {
    sessionStorage.removeItem(KEY(videoId));
  } catch {
    // Ignore.
  }
}

/** Waits for another tab or in-flight request to persist a job ID. */
export function waitForPendingJobId(
  videoId: string,
  timeoutMs = 60_000,
): Promise<string | null> {
  return new Promise((resolve) => {
    const deadline = Date.now() + timeoutMs;

    const tick = () => {
      const jobId = readPendingJobId(videoId);
      if (jobId) {
        resolve(jobId);
        return;
      }
      const handoff = readPendingJobHandoff(videoId);
      if (handoff !== "starting" && handoff === null) {
        resolve(null);
        return;
      }
      if (Date.now() >= deadline) {
        resolve(null);
        return;
      }
      setTimeout(tick, 200);
    };

    tick();
  });
}
