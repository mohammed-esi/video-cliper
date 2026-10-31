const BYTE_UNITS = ["B", "KB", "MB", "GB"] as const;

export function formatBytes(bytes: number): string {
  let value = bytes;
  let unit = 0;

  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }

  const digits = unit === 0 || value >= 10 ? 0 : 1;
  return `${value.toFixed(digits)} ${BYTE_UNITS[unit]}`;
}

function splitSeconds(seconds: number) {
  const tenths = Math.round(Math.max(seconds, 0) * 10);
  const whole = Math.floor(tenths / 10);
  return {
    hours: Math.floor(whole / 3600),
    minutes: Math.floor((whole % 3600) / 60),
    seconds: whole % 60,
    tenths: tenths % 10,
  };
}

/** Formats seconds as mm:ss.s, or h:mm:ss.s from one hour. */
export function formatTimecode(totalSeconds: number): string {
  const { hours, minutes, seconds, tenths } = splitSeconds(totalSeconds);
  const mm = String(minutes).padStart(2, "0");
  const ss = `${String(seconds).padStart(2, "0")}.${tenths}`;
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** Spoken form for screen readers, e.g. "1 minute 23.4 seconds". */
export function describeTimecode(totalSeconds: number): string {
  const { hours, minutes, seconds, tenths } = splitSeconds(totalSeconds);
  const parts: string[] = [];
  if (hours > 0) {
    parts.push(`${hours} ${hours === 1 ? "hour" : "hours"}`);
  }
  if (minutes > 0) {
    parts.push(`${minutes} ${minutes === 1 ? "minute" : "minutes"}`);
  }
  parts.push(`${seconds}.${tenths} seconds`);
  return parts.join(" ");
}

/**
 * Parses "83.4", "1:23.4" or "1:01:23.4" into seconds.
 * Returns null for anything else, including out-of-range minutes or seconds.
 */
export function parseTimecode(text: string): number | null {
  const parts = text.trim().split(":");
  const last = parts.at(-1) ?? "";
  const leading = parts.slice(0, -1);

  if (
    parts.length > 3 ||
    !/^\d+(\.\d*)?$/.test(last) ||
    leading.some((part) => !/^\d+$/.test(part))
  ) {
    return null;
  }

  const [seconds, minutes = 0, hours = 0] = parts.map(Number).reverse();
  if (
    (parts.length > 1 && seconds >= 60) ||
    (parts.length > 2 && minutes >= 60)
  ) {
    return null;
  }

  return hours * 3600 + minutes * 60 + seconds;
}
