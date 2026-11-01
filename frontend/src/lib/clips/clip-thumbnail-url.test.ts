import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  buildClipThumbnailPath,
  clipThumbnailRevision,
} from "./clip-thumbnail-url.ts";

describe("clip thumbnail URLs", () => {
  it("builds a revision from saved trim boundaries", () => {
    assert.equal(clipThumbnailRevision(45, 115), "45.0_115.0");
  });

  it("changes the path when the revision changes after a trim save", () => {
    const videoId = "00000000-0000-4000-8000-000000000099";
    const clipId = "00000000-0000-4000-8000-000000000001";
    const before = buildClipThumbnailPath(
      videoId,
      clipId,
      clipThumbnailRevision(60, 120),
    );
    const after = buildClipThumbnailPath(
      videoId,
      clipId,
      clipThumbnailRevision(50, 110),
    );
    assert.notEqual(before, after);
    assert.match(before, /[?&]v=60\.0_120\.0$/);
    assert.match(after, /[?&]v=50\.0_110\.0$/);
  });
});
