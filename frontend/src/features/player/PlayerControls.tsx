"use client";

import type { CSSProperties } from "react";
import {
  FastForward,
  Pause,
  Play,
  Repeat,
  Rewind,
  Volume2,
  VolumeX,
} from "lucide-react";

import { IconButton } from "@/components/ui/IconButton";
import { Timecode } from "@/components/ui/Timecode";
import { cn } from "@/lib/cn";
import { describeTimecode } from "@/lib/format";

export interface PlayerControlsProps {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  isMuted: boolean;
  isLooping: boolean;
  onPlayPause: () => void;
  onSeek: (time: number) => void;
  onMutedChange: (muted: boolean) => void;
  onLoopingChange: (looping: boolean) => void;
  /** Seconds moved by the back/forward buttons. */
  skipSeconds?: number;
  disabled?: boolean;
  className?: string;
}

/** Transport bar: seek bar, play/pause, skip, time read-out, loop and mute. */
export function PlayerControls({
  isPlaying,
  currentTime,
  duration,
  isMuted,
  isLooping,
  onPlayPause,
  onSeek,
  onMutedChange,
  onLoopingChange,
  skipSeconds = 5,
  disabled = false,
  className,
}: PlayerControlsProps) {
  const safeDuration = Math.max(duration, 0);
  const fill = safeDuration > 0 ? (currentTime / safeDuration) * 100 : 0;
  const seekBy = (delta: number) =>
    onSeek(Math.min(Math.max(currentTime + delta, 0), safeDuration));

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <input
        type="range"
        aria-label="Seek"
        min={0}
        max={safeDuration}
        step={0.1}
        value={Math.min(currentTime, safeDuration)}
        aria-valuetext={`${describeTimecode(currentTime)} of ${describeTimecode(safeDuration)}`}
        onChange={(event) => onSeek(Number(event.target.value))}
        disabled={disabled || safeDuration === 0}
        className="range-slider w-full"
        style={{ "--range-fill": `${fill}%` } as CSSProperties}
      />

      <div className="flex items-center gap-1">
        <IconButton
          label={`Back ${skipSeconds} seconds`}
          icon={<Rewind />}
          size="sm"
          onClick={() => seekBy(-skipSeconds)}
          disabled={disabled}
        />
        <IconButton
          label={isPlaying ? "Pause" : "Play"}
          icon={
            isPlaying ? (
              <Pause fill="currentColor" />
            ) : (
              <Play fill="currentColor" className="translate-x-px" />
            )
          }
          variant="primary"
          size="md"
          className="rounded-full!"
          onClick={onPlayPause}
          disabled={disabled}
        />
        <IconButton
          label={`Forward ${skipSeconds} seconds`}
          icon={<FastForward />}
          size="sm"
          onClick={() => seekBy(skipSeconds)}
          disabled={disabled}
        />

        <p className="ml-2 text-dense whitespace-nowrap text-fg-muted">
          <Timecode seconds={currentTime} className="text-fg" />
          <span aria-hidden> / </span>
          <span className="sr-only"> of </span>
          <Timecode seconds={safeDuration} />
        </p>

        <div className="ml-auto flex items-center gap-1">
          <IconButton
            label="Loop clip"
            icon={<Repeat />}
            size="sm"
            pressed={isLooping}
            onClick={() => onLoopingChange(!isLooping)}
            disabled={disabled}
          />
          <IconButton
            label={isMuted ? "Unmute" : "Mute"}
            icon={isMuted ? <VolumeX /> : <Volume2 />}
            size="sm"
            onClick={() => onMutedChange(!isMuted)}
            disabled={disabled}
          />
        </div>
      </div>
    </div>
  );
}
