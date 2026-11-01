/** Keeps the media element audio state aligned with UI (React muted prop can lag on mount). */
export function applyVideoAudioState(
  video: HTMLVideoElement,
  options: { muted: boolean; volume?: number },
): void {
  video.muted = options.muted;
  if (!options.muted) {
    video.volume = options.volume ?? 1;
  }
}
