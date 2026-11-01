import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  applyTrimEndChange,
  applyTrimStartChange,
  clampTimeToTrimWindow,
  normalizeTrimRange,
  shouldStopAtTrimEnd,
} from "./clip-trim.ts";

describe("normalizeTrimRange", () => {
  it("allows extending beyond generated boundaries", () => {
    const result = normalizeTrimRange(45, 115, 200);
    assert.equal(result.ok, true);
    if (result.ok) {
      assert.equal(result.range.start, 45);
      assert.equal(result.range.end, 115);
    }
  });

  it("rejects ranges past the source duration", () => {
    const result = normalizeTrimRange(0, 201, 200);
    assert.equal(result.ok, false);
  });

  it("rejects ranges shorter than 0.1 seconds", () => {
    const result = normalizeTrimRange(1, 1.05, 10);
    assert.equal(result.ok, false);
  });
});

describe("applyTrimStartChange", () => {
  it("shortens a clip from the start", () => {
    const result = applyTrimStartChange(
      { start: 60, end: 120 },
      75,
      200,
    );
    assert.equal(result.ok, true);
    if (result.ok) {
      assert.equal(result.range.start, 75);
      assert.equal(result.range.end, 120);
    }
  });
});

describe("applyTrimEndChange", () => {
  it("extends a clip end on the source timeline", () => {
    const result = applyTrimEndChange(
      { start: 60, end: 120 },
      130,
      200,
    );
    assert.equal(result.ok, true);
    if (result.ok) {
      assert.equal(result.range.end, 130);
    }
  });
});

describe("trim preview playback", () => {
  it("clamps seeks to the edited window", () => {
    const window = { start: 45, end: 115 };
    assert.equal(clampTimeToTrimWindow(10, window), 45);
    assert.equal(clampTimeToTrimWindow(200, window), 115);
  });

  it("stops at the edited end boundary", () => {
    const window = { start: 45, end: 115 };
    assert.equal(shouldStopAtTrimEnd(114.96, window), true);
    assert.equal(shouldStopAtTrimEnd(100, window), false);
  });
});
