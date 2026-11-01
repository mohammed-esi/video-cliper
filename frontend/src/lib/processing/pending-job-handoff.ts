const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export type PendingJobHandoff = "starting" | { jobId: string };

export function parsePendingJobHandoff(
  value: string | null,
): PendingJobHandoff | null {
  if (value === "starting") {
    return "starting";
  }
  if (value && UUID_PATTERN.test(value)) {
    return { jobId: value };
  }
  return null;
}
