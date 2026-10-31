/**
 * Client-side checks for the import step. They mirror the backend rules so
 * people get instant feedback; the backend stays authoritative.
 */
import { formatBytes } from "./format";

export const ACCEPTED_VIDEO_EXTENSIONS = [
  ".mp4",
  ".mov",
  ".mkv",
  ".webm",
  ".m4v",
] as const;

const YOUTUBE_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "music.youtube.com",
  "youtu.be",
]);

const VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/;

export type YoutubeUrlResult =
  | { ok: true; videoId: string; url: string }
  | { ok: false; message: string };

/** Validates a pasted link and rebuilds a canonical watch URL from its video ID. */
export function parseYoutubeUrl(input: string): YoutubeUrlResult {
  const trimmed = input.trim();

  if (!trimmed) {
    return { ok: false, message: "Paste a YouTube link to continue." };
  }

  // People often paste links without the scheme ("youtube.com/watch?v=…").
  const withScheme = /^[a-z][a-z\d+.-]*:\/\//i.test(trimmed)
    ? trimmed
    : `https://${trimmed}`;

  let url: URL;
  try {
    url = new URL(withScheme);
  } catch {
    return { ok: false, message: "This doesn't look like a web link." };
  }

  const isHttp = url.protocol === "https:" || url.protocol === "http:";
  if (!isHttp || !YOUTUBE_HOSTS.has(url.hostname.toLowerCase())) {
    return { ok: false, message: "Use a link from youtube.com or youtu.be." };
  }

  const [, section, pathId] = url.pathname.split("/");

  // Shorts are already vertical, and the clipper expects a landscape source.
  if (section === "shorts") {
    return {
      ok: false,
      message: "Shorts are already vertical. Use a regular YouTube video link.",
    };
  }

  let candidate: string | null | undefined;
  if (url.hostname === "youtu.be") {
    candidate = section;
  } else if (url.pathname === "/watch") {
    candidate = url.searchParams.get("v");
  } else if (section === "embed" || section === "live") {
    candidate = pathId;
  }

  if (!candidate || !VIDEO_ID_PATTERN.test(candidate)) {
    return {
      ok: false,
      message: "This link doesn't point to a single YouTube video.",
    };
  }

  return {
    ok: true,
    videoId: candidate,
    url: `https://www.youtube.com/watch?v=${candidate}`,
  };
}

/** Returns a user-facing problem with the file, or null when it can be uploaded. */
export function getVideoFileError(file: File, maxBytes?: number): string | null {
  const name = file.name.toLowerCase();
  const hasAcceptedExtension = ACCEPTED_VIDEO_EXTENSIONS.some((extension) =>
    name.endsWith(extension),
  );

  if (!hasAcceptedExtension) {
    return `"${file.name}" isn't a supported video. Use MP4, MOV, MKV, WebM or M4V.`;
  }

  if (file.size === 0) {
    return "This file is empty. Choose another video.";
  }

  if (maxBytes !== undefined && file.size > maxBytes) {
    return `This file is ${formatBytes(file.size)}. The limit is ${formatBytes(maxBytes)}.`;
  }

  return null;
}
