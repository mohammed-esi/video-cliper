import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { parsePendingJobHandoff } from "./pending-job-handoff.ts";

describe("parsePendingJobHandoff", () => {
  it("recognizes an in-flight start marker", () => {
    assert.equal(parsePendingJobHandoff("starting"), "starting");
  });

  it("recognizes a persisted job ID", () => {
    const jobId = "11111111-1111-4111-8111-111111111111";
    assert.deepEqual(parsePendingJobHandoff(jobId), { jobId });
  });

  it("ignores unknown values", () => {
    assert.equal(parsePendingJobHandoff(null), null);
    assert.equal(parsePendingJobHandoff(""), null);
    assert.equal(parsePendingJobHandoff("not-a-uuid"), null);
  });
});
