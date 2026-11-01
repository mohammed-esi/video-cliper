import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { resolveMissingJobRecovery } from "./missing-job-recovery.ts";

const JOB_ID = "11111111-1111-4111-8111-111111111111";

describe("resolveMissingJobRecovery", () => {
  it("prefers resuming a stored job ID", () => {
    assert.deepEqual(
      resolveMissingJobRecovery({ storedJobId: JOB_ID, clipCount: 3 }),
      { kind: "resume-job", jobId: JOB_ID },
    );
  });

  it("opens the editor when clips already exist and no job ID is stored", () => {
    assert.deepEqual(
      resolveMissingJobRecovery({ storedJobId: null, clipCount: 2 }),
      { kind: "open-editor" },
    );
  });

  it("requires an explicit user action when nothing can be recovered", () => {
    assert.deepEqual(
      resolveMissingJobRecovery({ storedJobId: null, clipCount: 0 }),
      { kind: "needs-user-action" },
    );
    assert.deepEqual(
      resolveMissingJobRecovery({ storedJobId: null, clipCount: null }),
      { kind: "needs-user-action" },
    );
  });
});
