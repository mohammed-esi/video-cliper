import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  mapControlsSeekTarget,
  resolvePlayerControlsTimes,
  sourceTimelineTimeFromVideo,
} from "./editor-playback-time.ts";

describe("portrait player seek bar mapping", () => {
  const trimRange = { start: 60, end: 120 };

  it("uses clip-local time on the seek bar for portrait preview", () => {
    const times = resolvePlayerControlsTimes({
      portraitPreviewActive: true,
      videoLocalTime: 15,
      videoDuration: 58,
      trimRange,
    });
    assert.equal(times.currentTime, 15);
    assert.equal(times.duration, 58);
  });

  it("does not mix source start offset into seek bar current time", () => {
    const wrongSourceBased = trimRange.start + 15;
    const times = resolvePlayerControlsTimes({
      portraitPreviewActive: true,
      videoLocalTime: 15,
      videoDuration: 60,
      trimRange,
    });
    assert.notEqual(times.currentTime, wrongSourceBased);
    assert.ok(times.currentTime <= times.duration);
  });

  it("maps seek bar input to local video time for portrait", () => {
    assert.equal(
      mapControlsSeekTarget({
        portraitPreviewActive: true,
        trimRange,
        seekBarTime: 22.5,
      }),
      22.5,
    );
  });

  it("still reports source timeline time for the trimmer playhead", () => {
    assert.equal(
      sourceTimelineTimeFromVideo({
        portraitPreviewActive: true,
        videoLocalTime: 10,
        trimRange,
      }),
      70,
    );
  });

  it("uses raw video times on the original source tab", () => {
    const times = resolvePlayerControlsTimes({
      portraitPreviewActive: false,
      videoLocalTime: 200,
      videoDuration: 600,
      trimRange,
    });
    assert.equal(times.currentTime, 200);
    assert.equal(times.duration, 600);
  });
});
