import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type { JobResponse } from "./types.ts";

function mapBatchExportJobProgress(job: JobResponse) {
  const result = job.result ?? {};
  const total =
    typeof result.total === "number" && result.total > 0
      ? result.total
      : typeof result.clip_count === "number"
        ? result.clip_count
        : 0;
  const currentIndex =
    typeof result.current_index === "number" ? result.current_index : 0;
  const phaseRaw = typeof result.phase === "string" ? result.phase : "";

  if (job.status === "failed") {
    return {
      phase: "failed",
      label: job.error_message ?? "Export failed.",
      currentIndex,
      total,
    };
  }

  if (job.status === "completed") {
    return {
      phase: "completed",
      label: "Export ready",
      currentIndex: total || currentIndex,
      total: total || currentIndex,
    };
  }

  if (phaseRaw === "packaging") {
    return {
      phase: "packaging",
      label: "Packaging ZIP…",
      currentIndex,
      total,
    };
  }

  if (total > 0 && currentIndex > 0) {
    return {
      phase: "rendering",
      label: `Processing clip ${currentIndex} of ${total}`,
      currentIndex,
      total,
    };
  }

  return {
    phase: "rendering",
    label: "Preparing export…",
    currentIndex,
    total,
  };
}

describe("batch export job progress", () => {
  it("shows clip index while processing", () => {
    const view = mapBatchExportJobProgress({
      job_id: "00000000-0000-4000-8000-000000000001",
      video_id: "00000000-0000-4000-8000-000000000002",
      operation: "batch_export_clips",
      status: "processing",
      progress: 0.4,
      created_at: "",
      updated_at: "",
      error_message: null,
      result: { phase: "rendering", current_index: 2, total: 5 },
    });
    assert.equal(view.label, "Processing clip 2 of 5");
  });
});
