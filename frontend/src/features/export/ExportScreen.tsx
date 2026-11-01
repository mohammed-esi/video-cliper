"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ListVideo } from "lucide-react";

import { AppHeader } from "@/components/layout/AppHeader";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { StatusPill } from "@/components/ui/StatusPill";
import { ClipCard } from "@/features/clips/ClipCard";
import {
  ApiRequestError,
  buildClipThumbnailUrl,
  clipThumbnailRevision,
  listVideoClips,
} from "@/lib/api";
import type { ClipMetadata } from "@/lib/api/types";
import { buildBatchExportDownloadUrl } from "@/lib/api/batch-export";
import { triggerPortraitDownload } from "@/lib/clips/clip-export";
import {
  readExportSelection,
  saveExportSelection,
} from "@/lib/export/export-selection";
import { formatTimecode } from "@/lib/format";

import { ExportBar } from "./ExportBar";
import { useBatchClipExport } from "./useBatchClipExport";

export interface ExportScreenProps {
  videoId: string;
}

function clipTitle(index: number): string {
  return `Clip ${index + 1}`;
}

export function ExportScreen({ videoId }: ExportScreenProps) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clips, setClips] = useState<ClipMetadata[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<string[]>([]);
  const { state: batchState, startExport, retry } = useBatchClipExport({
    videoId,
  });

  const load = useCallback(async (signal?: AbortSignal) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listVideoClips(videoId, signal);
      setClips(response.clips);
      const validIds = new Set(response.clips.map((clip) => clip.clip_id));
      const stored = readExportSelection(videoId) ?? [];
      setSelectedOrder(stored.filter((id) => validIds.has(id)));
    } catch (loadError) {
      if (signal?.aborted) {
        return;
      }
      setError(
        loadError instanceof ApiRequestError
          ? loadError.message
          : "We couldn't load clips for export.",
      );
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }, [videoId]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [videoId]);

  useEffect(() => {
    const controller = new AbortController();
    const task = window.setTimeout(() => {
      void load(controller.signal);
    }, 0);
    return () => {
      window.clearTimeout(task);
      controller.abort();
    };
  }, [load]);

  useEffect(() => {
    if (selectedOrder.length > 0) {
      saveExportSelection(videoId, selectedOrder);
    }
  }, [selectedOrder, videoId]);

  const clipsById = useMemo(() => {
    return Object.fromEntries(clips.map((clip) => [clip.clip_id, clip]));
  }, [clips]);

  const exportItems = useMemo(() => {
    return selectedOrder
      .map((id) => clipsById[id])
      .filter((clip): clip is ClipMetadata => clip !== undefined);
  }, [clipsById, selectedOrder]);

  const isExporting = batchState.status === "running";
  const exportingLabel =
    batchState.status === "running" ? batchState.progress.label : "Exporting…";

  const handleExport = useCallback(() => {
    const payload = exportItems.map((clip) => ({
      clip_id: clip.clip_id,
      trim_revision: clipThumbnailRevision(clip.start_time, clip.end_time),
    }));
    startExport(payload);
  }, [exportItems, startExport]);

  const editHref = `/videos/${encodeURIComponent(videoId)}/edit`;

  return (
    <>
      <AppHeader currentStep="export" fullWidth />
      <main
        id="main"
        className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-6 sm:px-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-fg">Export clips</h1>
            <p className="text-sm text-fg-muted">
              Download selected clips as portrait MP4 files in one ZIP.
            </p>
          </div>
          <ButtonLink href={editHref} variant="secondary" icon={<ArrowLeft />}>
            Back to editor
          </ButtonLink>
        </div>

        {isLoading ? (
          <Card className="p-6">
            <ProgressBar label="Loading clips…" value={undefined} />
          </Card>
        ) : null}

        {!isLoading && error ? (
          <ErrorState title="Export unavailable" message={error} onRetry={() => void load()} />
        ) : null}

        {!isLoading && !error && exportItems.length === 0 ? (
          <EmptyState
            icon={<ListVideo />}
            title="No clips selected"
            description="Choose clips in the editor, then continue to export."
            action={<ButtonLink href={editHref}>Go to editor</ButtonLink>}
          />
        ) : null}

        {!isLoading && !error && exportItems.length > 0 ? (
          <>
            {batchState.status === "failed" ? (
              <ErrorState
                size="sm"
                title="Export failed"
                message={batchState.message}
                onRetry={retry}
              />
            ) : null}

            {batchState.status === "running" ? (
              <Card className="flex flex-col gap-3 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusPill tone="info" pulse>
                    Export in progress
                  </StatusPill>
                  <span className="text-sm text-fg-muted">{exportingLabel}</span>
                </div>
                <ProgressBar
                  label={exportingLabel}
                  value={
                    batchState.progress.total > 0
                      ? batchState.progress.currentIndex /
                        batchState.progress.total
                      : undefined
                  }
                />
              </Card>
            ) : null}

            {batchState.status === "completed" ? (
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="text-sm font-medium text-fg">ZIP ready</p>
                  <p className="text-sm text-fg-muted">
                    Your download should start automatically. If it did not, use
                    the button to try again.
                  </p>
                </div>
                <Button
                  onClick={() => {
                    triggerPortraitDownload(
                      buildBatchExportDownloadUrl(videoId, batchState.jobId),
                    );
                  }}
                >
                  Download ZIP again
                </Button>
              </Card>
            ) : null}

            <ul className="flex flex-col gap-2">
              {exportItems.map((clip, index) => {
                const revision = clipThumbnailRevision(
                  clip.start_time,
                  clip.end_time,
                );
                return (
                  <li key={clip.clip_id}>
                    <ClipCard
                      title={clipTitle(index)}
                      start={clip.start_time}
                      end={clip.end_time}
                      thumbnailUrl={buildClipThumbnailUrl(
                        videoId,
                        clip.clip_id,
                        revision,
                      )}
                      isActive={false}
                      isSelected
                      onActivate={() => router.push(`${editHref}?clip=${clip.clip_id}`)}
                      onSelectedChange={() => {}}
                    />
                    <p className="sr-only">
                      Duration {formatTimecode(clip.end_time - clip.start_time)}
                    </p>
                  </li>
                );
              })}
            </ul>

            <ExportBar
              selectedCount={exportItems.length}
              totalCount={clips.length}
              onExportSelected={handleExport}
              isExporting={isExporting}
              exportingLabel={exportingLabel}
              className="rounded-md border border-border"
            />
          </>
        ) : null}
      </main>
    </>
  );
}
