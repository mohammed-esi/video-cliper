export const MIN_CLIP_TRIM_DURATION_SECONDS = 0.1;
export const TRIM_TIME_QUANTUM = 0.1;

export interface SourceTimeRange {
  start: number;
  end: number;
}

export type TrimValidationResult =
  | { ok: true; range: SourceTimeRange }
  | { ok: false; message: string };

export function roundTrimTime(seconds: number): number {
  return Math.round(seconds * 10) / 10;
}

export function normalizeTrimRange(
  start: number,
  end: number,
  sourceDuration: number,
  minDuration = MIN_CLIP_TRIM_DURATION_SECONDS,
): TrimValidationResult {
  if (end - start + 1e-6 < minDuration) {
    return {
      ok: false,
      message: `Clips must be at least ${minDuration.toFixed(1)} seconds long.`,
    };
  }

  const normalizedStart = roundTrimTime(start);
  const normalizedEnd = roundTrimTime(end);

  if (normalizedStart < 0) {
    return { ok: false, message: "Start time cannot be before 0:00." };
  }
  if (normalizedEnd > sourceDuration + 1e-6) {
    return {
      ok: false,
      message: "End time cannot be past the end of the source video.",
    };
  }
  if (normalizedEnd <= normalizedStart) {
    return { ok: false, message: "End time must be after the start time." };
  }
  return {
    ok: true,
    range: { start: normalizedStart, end: normalizedEnd },
  };
}

export function applyTrimStartChange(
  current: SourceTimeRange,
  nextStart: number,
  sourceDuration: number,
): TrimValidationResult {
  return normalizeTrimRange(nextStart, current.end, sourceDuration);
}

export function applyTrimEndChange(
  current: SourceTimeRange,
  nextEnd: number,
  sourceDuration: number,
): TrimValidationResult {
  return normalizeTrimRange(current.start, nextEnd, sourceDuration);
}

/** Keeps scrubbing inside an edited clip preview on the source timeline. */
export function clampTimeToTrimWindow(
  time: number,
  window: SourceTimeRange,
): number {
  return Math.min(Math.max(time, window.start), window.end);
}

export function shouldStopAtTrimEnd(
  currentTime: number,
  window: SourceTimeRange,
  epsilon = 0.05,
): boolean {
  return currentTime >= window.end - epsilon;
}
