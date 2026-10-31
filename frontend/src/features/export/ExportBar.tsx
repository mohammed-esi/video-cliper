import { FileArchive, FileOutput } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";

export interface ExportBarProps {
  selectedCount: number;
  totalCount: number;
  onExportSelected: () => void;
  /** Shows a "Download all (ZIP)" button when provided. */
  onDownloadZip?: () => void;
  /** While true, the export button shows progress and both actions are locked. */
  isExporting?: boolean;
  /** Replaces the default "Exporting…" label, e.g. "Exporting 2 of 3…". */
  exportingLabel?: string;
  isPreparingZip?: boolean;
  className?: string;
}

/** Bottom bar summarising the selection, with batch export actions. */
export function ExportBar({
  selectedCount,
  totalCount,
  onExportSelected,
  onDownloadZip,
  isExporting = false,
  exportingLabel = "Exporting…",
  isPreparingZip = false,
  className,
}: ExportBarProps) {
  const hasSelection = selectedCount > 0;
  const isBusy = isExporting || isPreparingZip;

  return (
    <div
      role="region"
      aria-label="Export"
      className={cn(
        "flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-t border-border bg-surface px-4 py-3 sm:px-6",
        className,
      )}
    >
      <div aria-live="polite" className="min-w-0">
        <p className="text-sm font-medium text-fg">
          {hasSelection
            ? `${selectedCount} of ${totalCount} ${totalCount === 1 ? "clip" : "clips"} selected`
            : "No clips selected"}
        </p>
        <p className="text-dense text-fg-muted">
          {hasSelection
            ? "Each clip is exported as a 9:16 MP4."
            : "Tick the clips you want to export."}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {onDownloadZip && (
          <Button
            variant="secondary"
            icon={<FileArchive />}
            onClick={onDownloadZip}
            isLoading={isPreparingZip}
            disabled={isBusy || totalCount === 0}
          >
            {isPreparingZip ? "Preparing ZIP…" : "Download all (ZIP)"}
          </Button>
        )}
        <Button
          icon={<FileOutput />}
          onClick={onExportSelected}
          isLoading={isExporting}
          disabled={isBusy || !hasSelection}
        >
          {isExporting
            ? exportingLabel
            : hasSelection
              ? `Export ${selectedCount} ${selectedCount === 1 ? "clip" : "clips"}`
              : "Export selected"}
        </Button>
      </div>
    </div>
  );
}
