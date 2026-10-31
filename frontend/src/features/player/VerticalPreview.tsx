import type { ReactNode } from "react";
import { Smartphone } from "lucide-react";

import { cn } from "@/lib/cn";

import { MediaStatusMessage, type MediaStatus } from "./MediaStatusMessage";

export interface VerticalPreviewProps {
  status: MediaStatus;
  /**
   * The rendered vertical picture (e.g. a canvas or video), shown when ready.
   * A direct canvas, video or img child is sized to fill the frame.
   */
  children?: ReactNode;
  title?: string;
  /** Shown under the frame, e.g. the clip name and length. */
  caption?: ReactNode;
  emptyTitle?: string;
  emptyDescription?: string;
  errorMessage?: string;
  onRetry?: () => void;
  className?: string;
}

/** A 9:16 phone-proportioned frame for previewing the exported clip. */
export function VerticalPreview({
  status,
  children,
  title = "Vertical preview",
  caption,
  emptyTitle = "No clip selected",
  emptyDescription = "Pick a clip to see how it will look in 9:16.",
  errorMessage = "The preview couldn't be shown.",
  onRetry,
  className,
}: VerticalPreviewProps) {
  return (
    <figure className={cn("flex flex-col gap-3", className)}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-fg">{title}</span>
        <span className="rounded-sm border border-border px-1.5 py-0.5 font-mono text-[11px] leading-none text-fg-muted">
          9:16
        </span>
      </div>

      <div
        data-theme="dark"
        className="relative aspect-[9/16] w-full overflow-hidden rounded-[1.25rem] bg-surface-sunken text-fg shadow-pop ring-1 ring-border"
      >
        {status === "ready" ? (
          <div className="absolute inset-0 [&>canvas]:size-full [&>img]:size-full [&>img]:object-cover [&>video]:size-full [&>video]:object-cover">
            {children}
          </div>
        ) : (
          <MediaStatusMessage
            status={status}
            emptyIcon={<Smartphone />}
            emptyTitle={emptyTitle}
            emptyDescription={emptyDescription}
            loadingLabel="Preparing preview…"
            errorMessage={errorMessage}
            onRetry={onRetry}
            compact
          />
        )}
      </div>

      {caption && (
        <figcaption className="text-dense text-fg-muted">{caption}</figcaption>
      )}
    </figure>
  );
}
