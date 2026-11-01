import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  clipStreamPath,
  resolveEditorStreamUrl,
  sourceStreamPath,
} from "./media-stream-paths.ts";

const BASE = "http://127.0.0.1:8000";
const VIDEO_ID = "22222222-2222-4222-8222-222222222222";
const CLIP_ID = "11111111-1111-4111-8111-111111111111";

describe("media stream paths", () => {
  it("builds clip and source paths", () => {
    assert.equal(
      clipStreamPath(VIDEO_ID, CLIP_ID),
      `/api/videos/${VIDEO_ID}/clips/${CLIP_ID}`,
    );
    assert.equal(
      sourceStreamPath(VIDEO_ID),
      `/api/videos/${VIDEO_ID}/source`,
    );
  });

  it("resolves clip stream URLs", () => {
    assert.equal(
      resolveEditorStreamUrl({
        baseUrl: BASE,
        videoId: VIDEO_ID,
        previewMode: "clip",
        clipId: CLIP_ID,
      }),
      `${BASE}/api/videos/${VIDEO_ID}/clips/${CLIP_ID}`,
    );
  });

  it("resolves source stream URLs", () => {
    assert.equal(
      resolveEditorStreamUrl({
        baseUrl: BASE,
        videoId: VIDEO_ID,
        previewMode: "source",
        clipId: null,
      }),
      `${BASE}/api/videos/${VIDEO_ID}/source`,
    );
  });

  it("returns undefined for clip mode without a clip ID", () => {
    assert.equal(
      resolveEditorStreamUrl({
        baseUrl: BASE,
        videoId: VIDEO_ID,
        previewMode: "clip",
        clipId: null,
      }),
      undefined,
    );
  });
});
