const STORAGE_PREFIX = "video-clipper:export-selection:";

export function exportSelectionStorageKey(videoId: string): string {
  return `${STORAGE_PREFIX}${videoId}`;
}

export function saveExportSelection(videoId: string, clipIds: string[]): void {
  if (typeof window === "undefined") {
    return;
  }
  const unique = [...new Set(clipIds)];
  window.sessionStorage.setItem(
    exportSelectionStorageKey(videoId),
    JSON.stringify(unique),
  );
}

export function readExportSelection(videoId: string): string[] | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.sessionStorage.getItem(exportSelectionStorageKey(videoId));
  if (!raw) {
    return null;
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return null;
    }
    return parsed.filter((value): value is string => typeof value === "string");
  } catch {
    return null;
  }
}

export function clearExportSelection(videoId: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.sessionStorage.removeItem(exportSelectionStorageKey(videoId));
}

export function buildExportScreenPath(videoId: string): string {
  return `/videos/${encodeURIComponent(videoId)}/export`;
}

export function toggleExportSelectionId(
  selectedIds: ReadonlySet<string>,
  clipId: string,
  selected: boolean,
): Set<string> {
  const next = new Set(selectedIds);
  if (selected) {
    next.add(clipId);
  } else {
    next.delete(clipId);
  }
  return next;
}

export function selectAllClipIds(clips: ReadonlyArray<{ id: string }>): Set<string> {
  return new Set(clips.map((clip) => clip.id));
}

export function pruneExportSelection(
  selectedIds: ReadonlySet<string>,
  validClipIds: ReadonlySet<string>,
): Set<string> {
  const next = new Set<string>();
  for (const id of selectedIds) {
    if (validClipIds.has(id)) {
      next.add(id);
    }
  }
  return next;
}
