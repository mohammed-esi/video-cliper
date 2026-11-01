import { getApiBaseUrl } from "./config";
import { clipStreamPath, sourceStreamPath } from "./media-stream-paths";

export type { EditorPreviewMode } from "./media-stream-paths";
export {
  clipStreamPath,
  resolveEditorStreamUrl,
  sourceStreamPath,
} from "./media-stream-paths";

export function buildClipStreamUrl(videoId: string, clipId: string): string {
  return `${getApiBaseUrl()}${clipStreamPath(videoId, clipId)}`;
}

export function buildSourceStreamUrl(videoId: string): string {
  return `${getApiBaseUrl()}${sourceStreamPath(videoId)}`;
}
