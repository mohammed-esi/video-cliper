import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type { JobResponse } from "../api/types.ts";

import {
  isProcessingSource,
  jobStatusMessage,
  mapJobToProgressView,
} from "./job-view-model.ts";

function sampleJob(overrides: Partial<JobResponse>): JobResponse {
  return {
    job_id: "11111111-1111-4111-8111-111111111111",
    video_id: "22222222-2222-4222-8222-222222222222",
    operation: "generate_clips",
    status: "queued",
    progress: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    error_message: null,
    result: null,
    ...overrides,
  };
}

describe("mapJobToProgressView", () => {
  it("maps queued jobs to processing stage without fake progress", () => {
    const view = mapJobToProgressView(sampleJob({ status: "queued" }));
    assert.equal(view.stage, "processing");
    assert.equal(view.progress, undefined);
    assert.equal(view.isTerminal, false);
    assert.match(view.message ?? "", /queue/i);
  });

  it("uses backend progress while processing", () => {
    const view = mapJobToProgressView(
      sampleJob({ status: "processing", progress: 0.42 }),
    );
    assert.equal(view.stage, "processing");
    assert.equal(view.progress, 0.42);
  });

  it("maps completed jobs to completed stage", () => {
    const view = mapJobToProgressView(
      sampleJob({ status: "completed", progress: 1 }),
    );
    assert.equal(view.stage, "completed");
    assert.equal(view.isTerminal, true);
  });

  it("surfaces failed jobs with a user-safe error", () => {
    const view = mapJobToProgressView(
      sampleJob({
        status: "failed",
        error_message: "FFmpeg failed.",
      }),
    );
    assert.equal(view.isTerminal, true);
    assert.equal(view.error, "FFmpeg failed.");
  });
});

describe("processing route helpers", () => {
  it("accepts upload and youtube sources", () => {
    assert.equal(isProcessingSource("upload"), true);
    assert.equal(isProcessingSource("youtube"), true);
    assert.equal(isProcessingSource("other"), false);
  });

  it("describes queued and processing statuses", () => {
    assert.match(jobStatusMessage("queued") ?? "", /queue/i);
    assert.match(jobStatusMessage("processing") ?? "", /clip/i);
    assert.equal(jobStatusMessage("completed"), undefined);
  });
});
