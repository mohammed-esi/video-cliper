import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { deriveClipThumbnailDisplayState } from "./clip-card-thumbnail-state.ts";

describe("deriveClipThumbnailDisplayState", () => {
  const url = "http://127.0.0.1:8000/api/videos/v/clips/c/thumbnail?v=1";

  it("shows loading while waiting for the image", () => {
    assert.equal(
      deriveClipThumbnailDisplayState({
        status: "ready",
        thumbnailUrl: url,
        loadedUrl: null,
        failedUrl: null,
        timedOut: false,
      }),
      "loading",
    );
  });

  it("shows ready after a successful load", () => {
    assert.equal(
      deriveClipThumbnailDisplayState({
        status: "ready",
        thumbnailUrl: url,
        loadedUrl: url,
        failedUrl: null,
        timedOut: false,
      }),
      "ready",
    );
  });

  it("shows error after load failure", () => {
    assert.equal(
      deriveClipThumbnailDisplayState({
        status: "ready",
        thumbnailUrl: url,
        loadedUrl: null,
        failedUrl: url,
        timedOut: false,
      }),
      "error",
    );
  });

  it("shows error after a load timeout", () => {
    assert.equal(
      deriveClipThumbnailDisplayState({
        status: "ready",
        thumbnailUrl: url,
        loadedUrl: null,
        failedUrl: null,
        timedOut: true,
      }),
      "error",
    );
  });
});
