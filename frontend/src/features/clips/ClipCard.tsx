import type { ReactNode } from "react";
import { Film, ImageOff, LoaderCircle } from "lucide-react";

import { cn } from "@/lib/cn";
import { formatTimecode } from "@/lib/format";

export type ClipCardStatus = "ready" | "loading" | "error";

export interface ClipCardProps {
  title: string;
  start: number;
  end: number;
  thumbnailUrl?: string;
  /** "loading" while the clip's preview is being prepared; "error" if it failed. */
  status?: ClipCardStatus;
  errorMessage?: string;
  /** The clip currently open in the editor. */
  isActive: boolean;
  /** Ticked for export. */
  isSelected: boolean;
  onActivate: () => void;
  onSelectedChange: (selected: boolean) => void;
  /** Usually a compact ClipExportControl. */
  exportSlot?: ReactNode;
  className?: string;
}

export function ClipCard({
  title,
  start,
  end,
  thumbnailUrl,
  status = "ready",
  errorMessage = "Preview unavailable",
  isActive,
  isSelected,
  onActivate,
  onSelectedChange,
  exportSlot,
  className,
}: ClipCardProps) {
  return (
    <article
      className={cn(
        "group relative flex gap-3 rounded-md border p-2.5",
        "transition-colors duration-(--dur-fast) ease-out",
        isActive
          ? "border-accent bg-accent-soft"
          : "border-border bg-surface hover:border-border-strong hover:bg-surface-raised",
        className,
      )}
    >
      <div className="relative aspect-video w-24 shrink-0 overflow-hidden rounded-sm bg-surface-sunken">
        {status === "ready" && thumbnailUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- served by the local backend, not optimisable by next/image
          <img
            src={thumbnailUrl}
            alt=""
            loading="lazy"
            className="size-full object-cover"
          />
        ) : (
          <span
            className={cn(
              "flex size-full items-center justify-center [&_svg]:size-5",
              status === "error" ? "text-danger" : "text-fg-subtle",
            )}
            aria-hidden
          >
            {status === "loading" ? (
              <LoaderCircle className="animate-spin" />
            ) : status === "error" ? (
              <ImageOff />
            ) : (
              <Film />
            )}
          </span>
        )}
        {/* Raised above the stretched activate button so it stays clickable. */}
        <label className="absolute top-1 left-1 z-10 flex cursor-pointer rounded-[4px] bg-black/60 p-1">
          <input
            type="checkbox"
            checked={isSelected}
            onChange={(event) => onSelectedChange(event.target.checked)}
            aria-label={`Select ${title} for export`}
            className="size-3.5 cursor-pointer accent-accent"
          />
        </label>
        <span className="absolute right-1 bottom-1 rounded-[3px] bg-black/75 px-1 font-mono text-[11px] leading-4 text-white tabular-nums">
          {formatTimecode(end - start)}
        </span>
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <button
          type="button"
          data-clip-activate
          onClick={onActivate}
          aria-current={isActive ? "true" : undefined}
          className={cn(
            "truncate text-left text-sm font-medium text-fg",
            // Stretch the hit area over the whole card; move the focus ring with it.
            "after:absolute after:inset-0 after:rounded-md after:content-['']",
            "focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-offset-2 focus-visible:after:outline-ring",
          )}
        >
          {title}
        </button>
        <p className="font-mono text-xs whitespace-nowrap text-fg-muted tabular-nums">
          {formatTimecode(start)} – {formatTimecode(end)}
        </p>
        {status === "error" && (
          <p className="truncate text-xs text-danger" title={errorMessage}>
            {errorMessage}
          </p>
        )}
        {exportSlot && <div className="relative z-10 mt-1.5">{exportSlot}</div>}
      </div>
    </article>
  );
}
