const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isClipUuid(value: string): boolean {
  return UUID_PATTERN.test(value);
}

/** Picks the clip to highlight after load or refresh. */
export function selectInitialClipId(
  clipIds: readonly string[],
  preferredId: string | null | undefined,
  currentId: string | null,
): string | null {
  if (clipIds.length === 0) {
    return null;
  }
  if (
    preferredId &&
    isClipUuid(preferredId) &&
    clipIds.includes(preferredId)
  ) {
    return preferredId;
  }
  if (currentId && clipIds.includes(currentId)) {
    return currentId;
  }
  return clipIds[0] ?? null;
}
