import type { SourceTimeRange } from "@/lib/clips/clip-trim";

/** Times for the transport seek bar (always 0 … duration within the active media). */
export interface PlayerControlsTimes {
  currentTime: number;
  duration: number;
}

/**
 * Portrait MP4s play from t=0; the trimmer still uses source timeline seconds.
 * The seek bar must use clip-local time, not source start + local (which breaks
 * when trimRange.start > 0).
 */
export function resolvePlayerControlsTimes(input: {
  portraitPreviewActive: boolean;
  videoLocalTime: number;
  videoDuration: number;
  trimRange: SourceTimeRange | null;
}): PlayerControlsTimes {
  if (input.portraitPreviewActive && input.trimRange) {
    const trimDuration = input.trimRange.end - input.trimRange.start;
    const duration =
      input.videoDuration > 0 ? input.videoDuration : trimDuration;
    return {
      currentTime: Math.min(Math.max(input.videoLocalTime, 0), duration),
      duration,
    };
  }
  return {
    currentTime: input.videoLocalTime,
    duration: input.videoDuration,
  };
}

export function mapControlsSeekTarget(input: {
  portraitPreviewActive: boolean;
  trimRange: SourceTimeRange | null;
  seekBarTime: number;
}): number {
  if (input.portraitPreviewActive && input.trimRange) {
    return Math.max(0, input.seekBarTime);
  }
  return input.seekBarTime;
}

export function sourceTimelineTimeFromVideo(input: {
  portraitPreviewActive: boolean;
  videoLocalTime: number;
  trimRange: SourceTimeRange | null;
}): number {
  if (input.portraitPreviewActive && input.trimRange) {
    return input.trimRange.start + input.videoLocalTime;
  }
  return input.videoLocalTime;
}
