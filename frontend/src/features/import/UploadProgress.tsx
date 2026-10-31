import { CircleAlert, FileVideo, RotateCcw, X } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { cn } from "@/lib/cn";
import { formatBytes } from "@/lib/format";

export interface UploadFileInfo {
  name: string;
  size: number;
}

export interface UploadProgressProps {
  file: UploadFileInfo;
  /** Fraction from 0 to 1; omit while the upload is starting. */
  progress?: number;
  /** When set, the upload failed and this message explains why. */
  error?: string | null;
  onCancel: () => void;
  onRetry: () => void;
}

export function UploadProgress({
  file,
  progress,
  error,
  onCancel,
  onRetry,
}: UploadProgressProps) {
  const hasFailed = Boolean(error);
  const uploadedText =
    progress === undefined
      ? "Starting…"
      : `${Math.round(progress * 100)}% · ${formatBytes(progress * file.size)} of ${formatBytes(file.size)}`;

  return (
    <div
      className={cn(
        "flex flex-col gap-5 rounded-lg border bg-bg p-5",
        hasFailed ? "border-danger/40" : "border-border",
      )}
    >
      <div className="flex items-center gap-3">
        <span
          className={cn(
            "flex size-10 shrink-0 items-center justify-center rounded-md",
            hasFailed ? "bg-danger-soft text-danger" : "bg-info-soft text-info",
          )}
          aria-hidden
        >
          <FileVideo className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg" title={file.name}>
            {file.name}
          </p>
          <p className="font-mono text-dense text-fg-muted tabular-nums">
            {formatBytes(file.size)}
          </p>
        </div>
        {!hasFailed && (
          <Button
            variant="ghost"
            size="sm"
            icon={<X />}
            onClick={onCancel}
            aria-label={`Cancel uploading ${file.name}`}
          >
            Cancel
          </Button>
        )}
      </div>

      {hasFailed ? (
        <>
          <p
            role="alert"
            className="flex items-start gap-2 text-sm text-danger"
          >
            <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            {error}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button icon={<RotateCcw />} onClick={onRetry}>
              Try again
            </Button>
            <Button variant="secondary" onClick={onCancel}>
              Choose another file
            </Button>
          </div>
        </>
      ) : (
        <ProgressBar
          label="Uploading"
          value={progress}
          valueText={uploadedText}
          tone="info"
        />
      )}
    </div>
  );
}
