export type EditorPreviewMode = "clip" | "source";

export function clipStreamPath(videoId: string, clipId: string): string {
  return `/api/videos/${encodeURIComponent(videoId)}/clips/${encodeURIComponent(clipId)}`;
}

export function sourceStreamPath(videoId: string): string {
  return `/api/videos/${encodeURIComponent(videoId)}/source`;
}

export function resolveEditorStreamUrl(input: {
  baseUrl: string;
  videoId: string;
  previewMode: EditorPreviewMode;
  clipId: string | null;
}): string | undefined {
  if (input.previewMode === "source") {
    return `${input.baseUrl}${sourceStreamPath(input.videoId)}`;
  }
  if (!input.clipId) {
    return undefined;
  }
  return `${input.baseUrl}${clipStreamPath(input.videoId, input.clipId)}`;
}
