import type { ComponentPropsWithRef } from "react";

import { cn } from "@/lib/cn";

export type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";

const toneClasses: Record<StatusTone, { pill: string; dot: string }> = {
  neutral: {
    pill: "border-border bg-surface-raised text-fg-muted",
    dot: "bg-fg-subtle",
  },
  info: { pill: "border-info/30 bg-info-soft text-info", dot: "bg-info" },
  success: {
    pill: "border-success/30 bg-success-soft text-success",
    dot: "bg-success",
  },
  warning: {
    pill: "border-warning/30 bg-warning-soft text-warning",
    dot: "bg-warning",
  },
  danger: {
    pill: "border-danger/30 bg-danger-soft text-danger",
    dot: "bg-danger",
  },
};

export interface StatusPillProps extends ComponentPropsWithRef<"span"> {
  tone?: StatusTone;
  /** Pulses the dot to show work in progress. */
  pulse?: boolean;
}

/** Compact status label. The text carries the meaning; colour only reinforces it. */
export function StatusPill({
  tone = "neutral",
  pulse = false,
  className,
  children,
  ...rest
}: StatusPillProps) {
  return (
    <span
      className={cn(
        "inline-flex h-7 items-center gap-2 rounded-full border px-3 text-dense font-medium whitespace-nowrap",
        toneClasses[tone].pill,
        className,
      )}
      {...rest}
    >
      <span
        className={cn(
          "size-2 shrink-0 rounded-full",
          toneClasses[tone].dot,
          pulse && "animate-pulse",
        )}
        aria-hidden
      />
      {children}
    </span>
  );
}
