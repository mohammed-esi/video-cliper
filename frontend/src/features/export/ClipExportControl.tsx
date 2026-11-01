import {
  CircleAlert,
  CircleCheck,
  Download,
  FileOutput,
  RotateCcw,
} from "lucide-react";

import { Button, ButtonLink, buttonStyles } from "@/components/ui/Button";
import { IconButton } from "@/components/ui/IconButton";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { cn } from "@/lib/cn";

export type ClipExportStatus =
  | { state: "idle" }
  /** Omit `progress` while the render is queued or starting. */
  | { state: "rendering"; progress?: number }
  | { state: "ready"; href: string; fileName?: string }
  | { state: "failed"; message?: string };

export interface ClipExportControlProps {
  status: ClipExportStatus;
  /** Names the clip in accessible labels, e.g. "Clip 3". */
  clipTitle: string;
  onExport: () => void;
  /** Defaults to `onExport`. */
  onRetry?: () => void;
  /** "sm" is a one-line control for clip cards; "md" suits the inspector. */
  size?: "sm" | "md";
  disabled?: boolean;
  className?: string;
}

/** Export, progress, download and retry for a single clip. */
export function ClipExportControl({
  status,
  clipTitle,
  onExport,
  onRetry = onExport,
  size = "md",
  disabled = false,
  className,
}: ClipExportControlProps) {
  return size === "sm" ? (
    <CompactControl
      status={status}
      clipTitle={clipTitle}
      onExport={onExport}
      onRetry={onRetry}
      disabled={disabled}
      className={className}
    />
  ) : (
    <div className={cn("flex flex-col gap-3", className)}>
      {status.state === "idle" && (
        <Button
          icon={<FileOutput />}
          fullWidth
          onClick={onExport}
          disabled={disabled}
        >
          Export 9:16 clip
        </Button>
      )}

      {status.state === "rendering" && (
        <div className="flex flex-col gap-2 rounded-md border border-border bg-bg p-3">
          <ProgressBar
            label="Rendering portrait"
            value={status.progress}
            valueText={
              status.progress === undefined ? "This may take a minute…" : undefined
            }
            tone="accent"
          />
          <p className="text-dense text-fg-muted">
            You can keep editing other clips meanwhile.
          </p>
        </div>
      )}

      {status.state === "ready" && (
        <>
          <p className="flex items-center gap-2 text-sm font-medium text-success">
            <CircleCheck className="size-4" aria-hidden />
            Ready to download
          </p>
          <ButtonLink
            href={status.href}
            download={status.fileName ?? true}
            icon={<Download />}
            fullWidth
          >
            Download MP4
          </ButtonLink>
        </>
      )}

      {status.state === "failed" && (
        <>
          <p
            role="alert"
            className="flex items-start gap-2 text-sm text-danger"
          >
            <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            {status.message ?? "The export didn't finish."}
          </p>
          <Button
            variant="secondary"
            icon={<RotateCcw />}
            fullWidth
            onClick={onRetry}
            disabled={disabled}
          >
            Try again
          </Button>
        </>
      )}
    </div>
  );
}

interface CompactControlProps {
  status: ClipExportStatus;
  clipTitle: string;
  onExport: () => void;
  onRetry: () => void;
  disabled: boolean;
  className?: string;
}

function CompactControl({
  status,
  clipTitle,
  onExport,
  onRetry,
  disabled,
  className,
}: CompactControlProps) {
  return (
    <div className={cn("flex h-8 items-center gap-2", className)}>
      {status.state === "idle" && (
        <Button
          variant="secondary"
          size="sm"
          icon={<FileOutput />}
          onClick={onExport}
          disabled={disabled}
          aria-label={`Export ${clipTitle}`}
        >
          Export
        </Button>
      )}

      {status.state === "rendering" && (
        <>
          <ProgressBar
            label={`Rendering ${clipTitle}`}
            value={status.progress}
            tone="accent"
            hideLabel
            className="max-w-24 min-w-10 flex-1"
          />
          <span className="sr-only">Rendering portrait</span>
        </>
      )}

      {status.state === "ready" && (
        <>
          <span className="flex items-center gap-1.5 text-dense font-medium text-success">
            <CircleCheck className="size-3.5" aria-hidden />
            Ready
          </span>
          <a
            href={status.href}
            download={status.fileName ?? true}
            aria-label={`Download ${clipTitle}`}
            title={`Download ${clipTitle}`}
            className={cn(
              buttonStyles({ variant: "secondary", size: "sm" }),
              "w-8 px-0!",
            )}
          >
            <Download aria-hidden />
          </a>
        </>
      )}

      {status.state === "failed" && (
        <>
          <span
            className="flex items-center gap-1.5 text-dense font-medium whitespace-nowrap text-danger"
            title={status.message}
          >
            <CircleAlert className="size-3.5" aria-hidden />
            Failed
          </span>
          <IconButton
            label={`Retry exporting ${clipTitle}`}
            icon={<RotateCcw />}
            variant="secondary"
            size="sm"
            onClick={onRetry}
            disabled={disabled}
          />
        </>
      )}
    </div>
  );
}
