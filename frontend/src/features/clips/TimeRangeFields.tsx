"use client";

import { useState, type KeyboardEvent } from "react";
import { CircleAlert, MapPin } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Timecode } from "@/components/ui/Timecode";
import { cn } from "@/lib/cn";
import { formatTimecode, parseTimecode } from "@/lib/format";

export interface TimeRangeFieldsProps {
  start: number;
  end: number;
  /** Used by the "Playhead" buttons. */
  currentTime: number;
  /** Shown as guidance only; validation happens in the caller. */
  minLength?: number;
  maxLength?: number;
  /** Problem with the range as a whole, e.g. overlapping another clip. */
  error?: string | null;
  disabled?: boolean;
  onStartChange: (time: number) => void;
  onEndChange: (time: number) => void;
  className?: string;
}

/** Start / end timecode fields with "set to playhead" shortcuts and a length read-out. */
export function TimeRangeFields({
  start,
  end,
  currentTime,
  minLength,
  maxLength,
  error,
  disabled = false,
  onStartChange,
  onEndChange,
  className,
}: TimeRangeFieldsProps) {
  const lengthHint =
    minLength !== undefined && maxLength !== undefined
      ? `Clips can be ${minLength}–${maxLength} s long.`
      : minLength !== undefined
        ? `Clips must be at least ${minLength} s long.`
        : maxLength !== undefined
          ? `Clips can be up to ${maxLength} s long.`
          : null;

  return (
    <fieldset
      disabled={disabled}
      className={cn("flex min-w-0 flex-col gap-4", className)}
    >
      <legend className="sr-only">Clip start and end</legend>
      <TimecodeField
        label="Start"
        value={start}
        currentTime={currentTime}
        onCommit={onStartChange}
      />
      <TimecodeField
        label="End"
        value={end}
        currentTime={currentTime}
        onCommit={onEndChange}
      />

      <div className="flex items-baseline justify-between gap-3 rounded-md border border-border bg-bg px-3 py-2.5">
        <span className="text-sm text-fg-muted">Length</span>
        <Timecode
          seconds={Math.max(end - start, 0)}
          className="text-base font-medium text-fg"
        />
      </div>

      {lengthHint && !error && (
        <p className="-mt-2 text-dense text-fg-muted">{lengthHint}</p>
      )}
      {error && (
        <p
          role="alert"
          className="-mt-2 flex items-start gap-1.5 text-dense text-danger"
        >
          <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {error}
        </p>
      )}
    </fieldset>
  );
}

interface TimecodeFieldProps {
  label: string;
  value: number;
  currentTime: number;
  onCommit: (time: number) => void;
}

function TimecodeField({
  label,
  value,
  currentTime,
  onCommit,
}: TimecodeFieldProps) {
  // While editing, the typed text is kept as a draft; otherwise the field
  // always shows the current value from props.
  const [draft, setDraft] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  function commit() {
    if (draft === null) {
      return;
    }
    const parsed = parseTimecode(draft);
    if (parsed === null) {
      setParseError("Use a time like 1:23.4 or 83.4.");
      return;
    }
    setParseError(null);
    setDraft(null);
    if (parsed !== value) {
      onCommit(parsed);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      commit();
    } else if (event.key === "Escape") {
      setDraft(null);
      setParseError(null);
    }
  }

  return (
    <Input
      label={label}
      value={draft ?? formatTimecode(value)}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={handleKeyDown}
      inputMode="decimal"
      autoComplete="off"
      spellCheck={false}
      className="font-mono tabular-nums"
      error={parseError}
      trailing={
        <Button
          variant="secondary"
          size="md"
          icon={<MapPin />}
          onClick={() => {
            setDraft(null);
            setParseError(null);
            onCommit(currentTime);
          }}
          aria-label={`Set ${label.toLowerCase()} to playhead`}
          title={`Set ${label.toLowerCase()} to playhead (${formatTimecode(currentTime)})`}
          // Match the 44px field height.
          className="h-11!"
        >
          Playhead
        </Button>
      }
    />
  );
}
