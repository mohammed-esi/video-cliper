import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { selectInitialClipId } from "./editor-selection.ts";

const CLIPS = [
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
] as const;

describe("selectInitialClipId", () => {
  it("selects the first clip by default", () => {
    assert.equal(selectInitialClipId(CLIPS, null, null), CLIPS[0]);
  });

  it("prefers a valid URL clip parameter", () => {
    assert.equal(selectInitialClipId(CLIPS, CLIPS[1], null), CLIPS[1]);
  });

  it("keeps the current clip when still present", () => {
    assert.equal(selectInitialClipId(CLIPS, null, CLIPS[1]), CLIPS[1]);
  });

  it("ignores invalid preferred IDs", () => {
    assert.equal(selectInitialClipId(CLIPS, "not-valid", null), CLIPS[0]);
  });

  it("returns null for an empty list", () => {
    assert.equal(selectInitialClipId([], CLIPS[0], CLIPS[0]), null);
  });
});
