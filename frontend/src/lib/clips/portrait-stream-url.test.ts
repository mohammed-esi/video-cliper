import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { clipThumbnailRevision } from "./clip-thumbnail-url.ts";

const VIDEO_ID = "22222222-2222-4222-8222-222222222222";
const CLIP_ID = "11111111-1111-4111-8111-111111111111";

describe("portrait stream URL", () => {
  it("uses the same saved-trim revision as thumbnails", () => {
    const revision = clipThumbnailRevision(12.5, 45.0);
    assert.equal(revision, "12.5_45.0");
    const path = `/api/videos/${encodeURIComponent(VIDEO_ID)}/clips/${encodeURIComponent(CLIP_ID)}/portrait?v=${revision}`;
    assert.match(path, /portrait\?v=12\.5_45\.0$/);
  });
});
