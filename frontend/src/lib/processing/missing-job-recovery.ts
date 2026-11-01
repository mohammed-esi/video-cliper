export type MissingJobRecovery =
  | { kind: "resume-job"; jobId: string }
  | { kind: "open-editor" }
  | { kind: "needs-user-action" };

/**
 * Decides how to recover processing when the URL has a video ID but no job ID.
 * Does not create jobs automatically.
 */
export function resolveMissingJobRecovery(input: {
  storedJobId: string | null;
  clipCount: number | null;
}): MissingJobRecovery {
  if (input.storedJobId) {
    return { kind: "resume-job", jobId: input.storedJobId };
  }
  if (input.clipCount !== null && input.clipCount > 0) {
    return { kind: "open-editor" };
  }
  return { kind: "needs-user-action" };
}
