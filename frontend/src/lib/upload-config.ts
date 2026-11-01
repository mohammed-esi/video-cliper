const DEFAULT_MAX_UPLOAD_BYTES = 500 * 1024 * 1024;

export function getMaxUploadBytes(): number {
  const raw = process.env.NEXT_PUBLIC_MAX_UPLOAD_BYTES?.trim();
  if (!raw) {
    return DEFAULT_MAX_UPLOAD_BYTES;
  }

  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return DEFAULT_MAX_UPLOAD_BYTES;
  }

  return parsed;
}
