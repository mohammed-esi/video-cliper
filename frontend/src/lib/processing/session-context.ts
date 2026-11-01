import type { ProcessingSource } from "./job-view-model";

export interface ProcessingSessionContext {
  source: ProcessingSource;
  videoTitle: string;
}

function storageKey(videoId: string): string {
  return `video-clipper:processing:${videoId}`;
}

export function saveProcessingSessionContext(
  videoId: string,
  context: ProcessingSessionContext,
): void {
  if (typeof sessionStorage === "undefined") {
    return;
  }
  try {
    sessionStorage.setItem(storageKey(videoId), JSON.stringify(context));
  } catch {
    // Ignore quota or privacy mode errors.
  }
}

export function readProcessingSessionContext(
  videoId: string,
): ProcessingSessionContext | null {
  if (typeof sessionStorage === "undefined") {
    return null;
  }
  try {
    const raw = sessionStorage.getItem(storageKey(videoId));
    if (!raw) {
      return null;
    }
    const parsed: unknown = JSON.parse(raw);
    const source = (parsed as ProcessingSessionContext).source;
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "source" in parsed &&
      (source === "upload" || source === "youtube")
    ) {
      const ctx = parsed as ProcessingSessionContext;
      if (typeof ctx.videoTitle === "string") {
        return ctx;
      }
    }
  } catch {
    return null;
  }
  return null;
}

export function clearProcessingSessionContext(videoId: string): void {
  if (typeof sessionStorage === "undefined") {
    return;
  }
  try {
    sessionStorage.removeItem(storageKey(videoId));
  } catch {
    // Ignore.
  }
}
