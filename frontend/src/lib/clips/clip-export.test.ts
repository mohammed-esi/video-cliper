import assert from "node:assert/strict";
import { describe, it } from "node:test";

function buildClipExportFileName(
  clipTitle: string,
  startTime: number,
  endTime: number,
): string {
  const safeTitle = clipTitle
    .trim()
    .replace(/[^\w\-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 40);
  const stem = safeTitle || "clip";
  return `${stem}_${startTime.toFixed(1)}-${endTime.toFixed(1)}.mp4`;
}

function exportTrimChanged(
  expectedRevision: string,
  currentRevision: string | null,
): boolean {
  return currentRevision !== expectedRevision;
}

describe("clip export helpers", () => {
  it("builds a readable export filename from clip title and trim", () => {
    assert.equal(
      buildClipExportFileName("Clip 2", 12.5, 45),
      "Clip-2_12.5-45.0.mp4",
    );
  });

  it("detects trim revision changes during export", () => {
    assert.equal(exportTrimChanged("10.0_20.0", "10.0_20.0"), false);
    assert.equal(exportTrimChanged("10.0_20.0", "11.0_20.0"), true);
    assert.equal(exportTrimChanged("10.0_20.0", null), true);
  });
});
