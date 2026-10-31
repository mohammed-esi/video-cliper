import type { ReactNode } from "react";
import { CircleAlert, LoaderCircle, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

export type MediaStatus = "empty" | "loading" | "ready" | "error";

export interface MediaStatusMessageProps {
  status: Exclude<MediaStatus, "ready">;
  emptyIcon: ReactNode;
  emptyTitle: string;
  emptyDescription?: string;
  loadingLabel: string;
  errorMessage: string;
  onRetry?: () => void;
  /** Tighter spacing for narrow frames such as the 9:16 preview. */
  compact?: boolean;
}

/** Centered empty / loading / error message for a media frame. */
export function MediaStatusMessage({
  status,
  emptyIcon,
  emptyTitle,
  emptyDescription,
  loadingLabel,
  errorMessage,
  onRetry,
  compact = false,
}: MediaStatusMessageProps) {
  return (
    <div
      className={cn(
        "absolute inset-0 flex flex-col items-center justify-center text-center",
        // Small stages (container under 20rem) drop secondary details to fit.
        compact ? "gap-2 p-4" : "gap-3 p-6 @max-xs:gap-2 @max-xs:p-3",
        // Over a poster frame, a scrim keeps the message readable.
        status === "loading" && "bg-surface-sunken/70",
      )}
    >
      {status === "loading" && (
        <div role="status" className="flex flex-col items-center gap-3">
          <LoaderCircle
            className="size-7 animate-spin text-fg-muted"
            aria-hidden
          />
          <span className="text-sm text-fg-muted">{loadingLabel}</span>
        </div>
      )}

      {status === "empty" && (
        <>
          <span
            className={cn(
              "flex items-center justify-center rounded-full bg-surface-raised text-fg-muted @max-xs:hidden",
              compact ? "size-10 [&_svg]:size-5" : "size-12 [&_svg]:size-6",
            )}
            aria-hidden
          >
            {emptyIcon}
          </span>
          <p className="text-sm font-medium text-fg">{emptyTitle}</p>
          {emptyDescription && (
            <p className="max-w-xs text-dense text-fg-muted @max-xs:hidden">
              {emptyDescription}
            </p>
          )}
        </>
      )}

      {status === "error" && (
        <>
          <CircleAlert
            className={cn(
              "text-danger @max-xs:hidden",
              compact ? "size-6" : "size-7",
            )}
            aria-hidden
          />
          <p role="alert" className="max-w-xs text-sm text-fg">
            {errorMessage}
          </p>
          {onRetry && (
            <Button
              variant="secondary"
              size="sm"
              icon={<RotateCcw />}
              onClick={onRetry}
            >
              Try again
            </Button>
          )}
        </>
      )}
    </div>
  );
}
