import type { ReactNode } from "react";
import { CircleAlert, RotateCcw } from "lucide-react";

import { cn } from "@/lib/cn";

import { Button } from "./Button";

export interface ErrorStateProps {
  title?: string;
  /** Plain-language cause and, ideally, what to do next. */
  message: ReactNode;
  /** Shows a "Try again" button when provided. */
  onRetry?: () => void;
  retryLabel?: string;
  /** Another way forward, e.g. a "Start over" button. */
  secondaryAction?: ReactNode;
  size?: "sm" | "md";
  className?: string;
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  retryLabel = "Try again",
  secondaryAction,
  size = "md",
  className,
}: ErrorStateProps) {
  const isSmall = size === "sm";

  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center text-center",
        isSmall ? "gap-2 px-4 py-8" : "gap-3 px-6 py-12",
        className,
      )}
    >
      <span
        className={cn(
          "mb-1 flex items-center justify-center rounded-full bg-danger-soft text-danger",
          isSmall ? "size-10 [&_svg]:size-5" : "size-12 [&_svg]:size-6",
        )}
        aria-hidden
      >
        <CircleAlert />
      </span>
      <p
        className={cn("font-medium text-fg", isSmall ? "text-sm" : "text-base")}
      >
        {title}
      </p>
      <p
        className={cn(
          "max-w-sm text-fg-muted",
          isSmall ? "text-dense" : "text-sm",
        )}
      >
        {message}
      </p>
      {(onRetry || secondaryAction) && (
        <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
          {onRetry && (
            <Button
              icon={<RotateCcw />}
              size={isSmall ? "sm" : "md"}
              onClick={onRetry}
            >
              {retryLabel}
            </Button>
          )}
          {secondaryAction}
        </div>
      )}
    </div>
  );
}
