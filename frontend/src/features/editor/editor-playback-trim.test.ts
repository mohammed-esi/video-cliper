import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  clampTimeToTrimWindow,
  shouldStopAtTrimEnd,
} from "../../lib/clips/clip-trim.ts";

describe("editor playback trim boundaries", () => {
  it("pauses preview at the edited end time", () => {
    const window = { start: 60, end: 120 };
    assert.equal(shouldStopAtTrimEnd(119.98, window), true);
  });

  it("keeps scrubbing inside the edited window", () => {
    const window = { start: 45, end: 115 };
    assert.equal(clampTimeToTrimWindow(20, window), 45);
    assert.equal(clampTimeToTrimWindow(999, window), 115);
  });
});
