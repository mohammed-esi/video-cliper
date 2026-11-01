import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { applyVideoAudioState } from "./video-audio.ts";

describe("applyVideoAudioState", () => {
  it("clears muted and restores volume when unmuting", () => {
    const video = {
      muted: true,
      volume: 0,
    } as HTMLVideoElement;

    applyVideoAudioState(video, { muted: false, volume: 1 });

    assert.equal(video.muted, false);
    assert.equal(video.volume, 1);
  });

  it("mutes without changing volume logic when muted", () => {
    const video = {
      muted: false,
      volume: 0.5,
    } as HTMLVideoElement;

    applyVideoAudioState(video, { muted: true });

    assert.equal(video.muted, true);
    assert.equal(video.volume, 0.5);
  });
});
