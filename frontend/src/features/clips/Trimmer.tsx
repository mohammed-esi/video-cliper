"use client";

import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";

import { Timecode } from "@/components/ui/Timecode";
import { cn } from "@/lib/cn";
import { describeTimecode, formatTimecode } from "@/lib/format";

export interface TimeRange {
  start: number;
  end: number;
}

export interface TrimmerSegment extends TimeRange {
  id: string;
  /** Short marker shown on the segment, e.g. the clip number. */
  label?: string;
}

export interface TrimmerProps {
  duration: number;
  /** The clip being edited. */
  value: TimeRange;
  currentTime: number;
  /** Other clips, drawn faintly for context. */
  segments?: ReadonlyArray<TrimmerSegment>;
  /** Handles can't make the clip shorter or longer than these. */
  minLength?: number;
  maxLength?: number;
  /** Keyboard nudge in seconds; Shift or Page keys use `largeStep`. */
  step?: number;
  largeStep?: number;
  /** Names the handles for screen readers, e.g. "Clip 3". */
  label?: string;
  disabled?: boolean;
  /** Fires continuously while a handle moves. */
  onChange: (range: TimeRange) => void;
  /** Fires once a drag or key press finishes. */
  onChangeEnd?: (range: TimeRange) => void;
  onSeek: (time: number) => void;
  className?: string;
}

type ViewMode = "clip" | "full";
type DragKind = "start" | "end" | "seek";
type View = readonly [number, number];

const TICK_INTERVALS = [
  0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600,
];

const clamp = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max);

function getClipView(range: TimeRange, duration: number): View {
  const padding = Math.max((range.end - range.start) * 0.5, 2);
  return [
    Math.max(0, range.start - padding),
    Math.min(duration, range.end + padding),
  ];
}

function getTicks([from, to]: View) {
  const interval =
    TICK_INTERVALS.find((candidate) => candidate >= (to - from) / 8) ??
    TICK_INTERVALS[TICK_INTERVALS.length - 1];
  const minor = interval / 2;
  const ticks: Array<{ time: number; major: boolean }> = [];

  for (let time = Math.ceil(from / minor) * minor; time <= to; time += minor) {
    const rounded = Number(time.toFixed(3));
    ticks.push({ time: rounded, major: rounded % interval === 0 });
  }
  return { ticks, interval };
}

/**
 * Timeline with start/end trim handles and a playhead. "Clip" view zooms to the
 * clip for precise trimming; "Full video" shows the whole source with other clips.
 */
export function Trimmer({
  duration,
  value,
  currentTime,
  segments = [],
  minLength = 1,
  maxLength = Number.POSITIVE_INFINITY,
  step = 0.1,
  largeStep = 1,
  label = "Clip",
  disabled = false,
  onChange,
  onChangeEnd,
  onSeek,
  className,
}: TrimmerProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<ViewMode>("clip");
  // The view is frozen during a drag so the scale doesn't shift under the pointer.
  const [drag, setDrag] = useState<{ kind: DragKind; view: View } | null>(null);

  const liveView: View =
    mode === "full" ? [0, duration] : getClipView(value, duration);
  const view = drag?.view ?? liveView;
  const viewLength = Math.max(view[1] - view[0], step);
  const toPercent = (time: number) => ((time - view[0]) / viewLength) * 100;

  const roundToStep = (time: number) =>
    Number((Math.round(time / step) * step).toFixed(3));

  const startBounds: View = [
    Math.max(0, value.end - maxLength),
    value.end - minLength,
  ];
  const endBounds: View = [
    value.start + minLength,
    Math.min(duration, value.start + maxLength),
  ];

  function rangeWith(kind: "start" | "end", time: number): TimeRange {
    const [min, max] = kind === "start" ? startBounds : endBounds;
    const next = clamp(roundToStep(time), min, max);
    return kind === "start"
      ? { start: next, end: value.end }
      : { start: value.start, end: next };
  }

  function timeAt(clientX: number, atView: View) {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) {
      return atView[0];
    }
    const fraction = clamp((clientX - rect.left) / rect.width, 0, 1);
    return atView[0] + fraction * (atView[1] - atView[0]);
  }

  function handlePointerDown(kind: DragKind, event: PointerEvent<HTMLElement>) {
    if (disabled || event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    if (kind !== "seek") {
      event.currentTarget.focus();
    }
    setDrag({ kind, view });
    if (kind === "seek") {
      onSeek(roundToStep(timeAt(event.clientX, view)));
    }
  }

  function handlePointerMove(event: PointerEvent<HTMLElement>) {
    if (!drag) {
      return;
    }
    const time = timeAt(event.clientX, drag.view);
    if (drag.kind === "seek") {
      onSeek(roundToStep(time));
    } else {
      onChange(rangeWith(drag.kind, time));
    }
  }

  function handlePointerUp() {
    if (drag && drag.kind !== "seek") {
      onChangeEnd?.(value);
    }
    setDrag(null);
  }

  function handleKeyDown(kind: "start" | "end", event: KeyboardEvent) {
    const current = kind === "start" ? value.start : value.end;
    const big = event.shiftKey ? largeStep : step;
    const target = {
      ArrowLeft: current - big,
      ArrowDown: current - big,
      ArrowRight: current + big,
      ArrowUp: current + big,
      PageDown: current - largeStep,
      PageUp: current + largeStep,
      Home: Number.NEGATIVE_INFINITY,
      End: Number.POSITIVE_INFINITY,
    }[event.key];

    if (target === undefined || disabled) {
      return;
    }
    event.preventDefault();
    const range = rangeWith(kind, target);
    onChange(range);
    onChangeEnd?.(range);
  }

  const { ticks, interval } = getTicks(view);
  const formatTick = (time: number) =>
    interval < 1 ? formatTimecode(time) : formatTimecode(time).slice(0, -2);
  const regionLeft = toPercent(value.start);
  const regionWidth = toPercent(value.end) - regionLeft;
  const playheadPercent = toPercent(currentTime);
  const isPlayheadVisible = playheadPercent >= 0 && playheadPercent <= 100;

  const handleClasses =
    "absolute inset-y-0 z-10 flex w-3 cursor-ew-resize touch-none items-center justify-center bg-accent " +
    "transition-colors duration-(--dur-fast) hover:bg-accent-hover focus-visible:outline-offset-1 " +
    // Widen the hit area beyond the 12px visual.
    "before:absolute before:-inset-x-2 before:inset-y-0 before:content-['']";

  return (
    <div
      className={cn("flex flex-col gap-3", disabled && "opacity-60", className)}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-fg-muted">
          <span className="font-medium text-fg">Timeline</span>
          <span aria-hidden> · </span>
          <Timecode seconds={value.end - value.start} className="text-fg" />
          <span className="sr-only"> selected</span>
        </p>
        <div
          role="group"
          aria-label="Timeline zoom"
          className="flex rounded-md border border-border bg-bg p-0.5"
        >
          {(
            [
              ["clip", "Clip"],
              ["full", "Full video"],
            ] as const
          ).map(([id, text]) => (
            <button
              key={id}
              type="button"
              aria-pressed={mode === id}
              onClick={() => setMode(id)}
              className={cn(
                "h-7 rounded-sm px-2.5 text-dense font-medium transition-colors duration-(--dur-fast)",
                mode === id
                  ? "bg-surface-raised text-fg shadow-sm"
                  : "text-fg-muted hover:text-fg",
              )}
            >
              {text}
            </button>
          ))}
        </div>
      </div>

      {/* Horizontal padding leaves room for the handles at the very ends. */}
      <div className="relative px-3 select-none">
        <div className="relative h-6" aria-hidden>
          {ticks.map(({ time, major }) => {
            const left = toPercent(time);
            return (
              <div
                key={time}
                className="absolute bottom-0"
                style={{ left: `${left}%` }}
              >
                <span
                  className={cn(
                    "absolute bottom-0 w-px",
                    major ? "h-2 bg-fg-subtle" : "h-1 bg-border-strong",
                  )}
                />
                {major && left > 3 && left < 97 && (
                  <span className="absolute bottom-2.5 -translate-x-1/2 font-mono text-[11px] text-fg-muted tabular-nums">
                    {formatTick(time)}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        <div
          ref={trackRef}
          onPointerDown={(event) => handlePointerDown("seek", event)}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          className={cn(
            "relative h-16 touch-none rounded-md border border-border bg-surface-sunken",
            disabled ? "cursor-not-allowed" : "cursor-pointer",
          )}
        >
          <div
            className="absolute inset-0 overflow-hidden rounded-md"
            aria-hidden
          >
            {segments.map((segment) => (
              <div
                key={segment.id}
                className="absolute inset-y-2 overflow-hidden rounded-sm border border-border-strong bg-surface-hover px-1.5"
                style={{
                  // A 2px gap keeps neighbouring clips visually separate.
                  left: `calc(${toPercent(segment.start)}% + 1px)`,
                  width: `calc(${toPercent(segment.end) - toPercent(segment.start)}% - 2px)`,
                }}
              >
                {segment.label && (
                  <span className="font-mono text-[11px] leading-6 text-fg-subtle">
                    {segment.label}
                  </span>
                )}
              </div>
            ))}
          </div>

          <div
            className="absolute inset-y-0 border-y-2 border-accent bg-accent-soft"
            style={{ left: `${regionLeft}%`, width: `${regionWidth}%` }}
            aria-hidden
          >
            {regionWidth > 12 && (
              <span className="absolute inset-x-0 bottom-1.5 truncate text-center font-mono text-[11px] text-accent tabular-nums">
                {formatTimecode(value.start)} – {formatTimecode(value.end)}
              </span>
            )}
          </div>

          {(["start", "end"] as const).map((kind) => {
            const time = kind === "start" ? value.start : value.end;
            const [min, max] = kind === "start" ? startBounds : endBounds;
            return (
              <div
                key={kind}
                role="slider"
                tabIndex={disabled ? -1 : 0}
                aria-label={`${label} ${kind}`}
                aria-valuemin={Number(min.toFixed(1))}
                aria-valuemax={Number(max.toFixed(1))}
                aria-valuenow={Number(time.toFixed(1))}
                aria-valuetext={describeTimecode(time)}
                aria-disabled={disabled || undefined}
                onPointerDown={(event) => handlePointerDown(kind, event)}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerCancel={handlePointerUp}
                onKeyDown={(event) => handleKeyDown(kind, event)}
                className={cn(
                  handleClasses,
                  kind === "start"
                    ? "-translate-x-full rounded-l-md"
                    : "rounded-r-md",
                )}
                style={{ left: `${toPercent(time)}%` }}
              >
                <span className="flex gap-0.5" aria-hidden>
                  <span className="h-5 w-px bg-accent-fg/60" />
                  <span className="h-5 w-px bg-accent-fg/60" />
                </span>
              </div>
            );
          })}
        </div>

        {isPlayheadVisible && (
          <div
            className="pointer-events-none absolute top-1 bottom-0 z-20 w-0.5 -translate-x-1/2 bg-playhead"
            style={{
              left: `calc(0.75rem + (100% - 1.5rem) * ${playheadPercent / 100})`,
            }}
            aria-hidden
          >
            <span className="absolute -top-1 left-1/2 size-2.5 -translate-x-1/2 rotate-45 rounded-[2px] bg-playhead" />
          </div>
        )}
      </div>
    </div>
  );
}
