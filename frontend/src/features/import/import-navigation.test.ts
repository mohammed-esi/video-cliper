import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type { ImportState } from "./ImportPanel.ts";
import {
  FRESH_IMPORT_QUERY_PARAM,
  buildFreshImportHomePath,
  resolveImportScreenMountKey,
} from "./import-navigation.ts";

const STALE_HANDOFF: ImportState = {
  status: "starting-processing",
  source: "youtube",
  label: "previous-video.mp4",
  video: {
    video_id: "00000000-0000-4000-8000-000000000001",
    original_filename: "previous-video.mp4",
    duration_seconds: 60,
    width: 1280,
    height: 720,
    has_audio: true,
    container: "mp4",
  },
};

/** Models React keyed remount: new key → fresh initial state only. */
function stateAfterImportNavigation(input: {
  cachedState: ImportState;
  previousMountKey: string;
  nextMountKey: string;
  initialState: ImportState;
}): ImportState {
  if (input.previousMountKey === input.nextMountKey) {
    return input.cachedState;
  }
  return input.initialState;
}

describe("import navigation", () => {
  it("builds a home path with the fresh-import query param", () => {
    const path = buildFreshImportHomePath("nonce-42");
    assert.equal(path, "/?freshImport=nonce-42");
    const params = new URLSearchParams(path.slice(2));
    assert.equal(params.get(FRESH_IMPORT_QUERY_PARAM), "nonce-42");
  });

  it("uses a stable mount key for plain home visits", () => {
    assert.equal(
      resolveImportScreenMountKey(new URLSearchParams()),
      "default",
    );
  });

  it("uses the query value as the mount key for fresh import", () => {
    const params = new URLSearchParams("freshImport=1730000000123");
    assert.equal(resolveImportScreenMountKey(params), "1730000000123");
  });
});

describe("ImportScreen keyed remount contract", () => {
  it("keeps stale handoff UI when remount key does not change", () => {
    const next = stateAfterImportNavigation({
      cachedState: STALE_HANDOFF,
      previousMountKey: "default",
      nextMountKey: "default",
      initialState: { status: "idle" },
    });
    assert.equal(next.status, "starting-processing");
  });

  it("resets to idle when fresh-import navigation changes the mount key", () => {
    const next = stateAfterImportNavigation({
      cachedState: STALE_HANDOFF,
      previousMountKey: "default",
      nextMountKey: "1730000000123",
      initialState: { status: "idle" },
    });
    assert.equal(next.status, "idle");
  });

  it("maps editor return navigation to a new mount key", () => {
    const cachedKey = resolveImportScreenMountKey(new URLSearchParams());
    const returnPath = buildFreshImportHomePath(99);
    const returnKey = resolveImportScreenMountKey(
      new URLSearchParams(returnPath.slice(2)),
    );
    assert.notEqual(cachedKey, returnKey);
  });
});
