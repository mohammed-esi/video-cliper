import { cn } from "@/lib/cn";

type ProgressTone = "accent" | "info" | "success" | "danger";

const toneClasses: Record<ProgressTone, string> = {
  accent: "bg-accent",
  info: "bg-info",
  success: "bg-success",
  danger: "bg-danger",
};

export interface ProgressBarProps {
  /** Accessible name; also shown above the bar unless `hideLabel` is set. */
  label: string;
  /** Fraction from 0 to 1. Omit while the total is unknown (indeterminate). */
  value?: number;
  /** Replaces the default percentage, e.g. "42% · 120 MB of 300 MB". */
  valueText?: string;
  tone?: ProgressTone;
  hideLabel?: boolean;
  className?: string;
}

export function ProgressBar({
  label,
  value,
  valueText,
  tone = "info",
  hideLabel = false,
  className,
}: ProgressBarProps) {
  const isIndeterminate = value === undefined;
  const fraction = isIndeterminate ? 0 : Math.min(Math.max(value, 0), 1);
  const percent = Math.round(fraction * 100);
  const displayText =
    valueText ?? (isIndeterminate ? undefined : `${percent}%`);

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {!hideLabel && (
        <div className="flex items-baseline justify-between gap-3 text-dense">
          <span className="font-medium text-fg">{label}</span>
          {displayText && (
            <span className="font-mono text-fg-muted tabular-nums">
              {displayText}
            </span>
          )}
        </div>
      )}
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={isIndeterminate ? undefined : percent}
        aria-valuetext={displayText}
        className="relative h-1.5 overflow-hidden rounded-full bg-surface-sunken"
      >
        {isIndeterminate ? (
          <div
            className={cn(
              "absolute inset-y-0 left-0 w-2/5 rounded-full animate-progress-indeterminate",
              toneClasses[tone],
            )}
          />
        ) : (
          <div
            className={cn(
              "h-full origin-left rounded-full transition-transform duration-(--dur-slow) ease-out",
              toneClasses[tone],
            )}
            style={{ transform: `scaleX(${fraction})` }}
          />
        )}
      </div>
    </div>
  );
}
