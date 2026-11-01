export type ClipCardStatus = "ready" | "loading" | "error";

export type ClipThumbnailDisplayState = "idle" | "loading" | "ready" | "error";

export function deriveClipThumbnailDisplayState(input: {
  status: ClipCardStatus;
  thumbnailUrl?: string;
  loadedUrl: string | null;
  failedUrl: string | null;
  timedOut: boolean;
}): ClipThumbnailDisplayState {
  if (input.status !== "ready" || !input.thumbnailUrl) {
    return input.status === "loading" ? "loading" : "idle";
  }
  if (input.loadedUrl === input.thumbnailUrl) {
    return "ready";
  }
  if (input.failedUrl === input.thumbnailUrl || input.timedOut) {
    return "error";
  }
  return "loading";
}

/** Lazy images inside hidden containers may never start loading in browsers. */
export const CLIP_THUMBNAIL_IMG_LOADING: "eager" | "lazy" = "eager";

export const CLIP_THUMBNAIL_LOAD_TIMEOUT_MS = 45_000;
