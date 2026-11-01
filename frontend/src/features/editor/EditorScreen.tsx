"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ListVideo } from "lucide-react";

import { AppHeader } from "@/components/layout/AppHeader";
import { EditorLayout } from "@/components/layout/EditorLayout";
import { FreshImportLink } from "@/features/import/FreshImportLink";
import { navigateToFreshImport } from "@/features/import/import-navigation";
import { EmptyState } from "@/components/ui/EmptyState";
import { StatusPill } from "@/components/ui/StatusPill";
import { ClipList, type ClipListItem } from "@/features/clips/ClipList";
import {
  TimeRangeFields,
} from "@/features/clips/TimeRangeFields";
import { Trimmer, type TrimmerSegment } from "@/features/clips/Trimmer";
import type { EditorPreviewMode } from "@/lib/api/media-stream-paths";
import {
  ApiRequestError,
  buildClipThumbnailUrl,
  clipThumbnailRevision,
  listVideoClips,
} from "@/lib/api";
import type { ClipMetadata } from "@/lib/api/types";
import {
  MIN_CLIP_TRIM_DURATION_SECONDS,
  applyTrimEndChange,
  applyTrimStartChange,
} from "@/lib/clips/clip-trim";
import { formatTimecode } from "@/lib/format";
import { isUuid } from "@/lib/ids";
import {
  buildExportScreenPath,
  clearExportSelection,
  pruneExportSelection,
  saveExportSelection,
} from "@/lib/export/export-selection";

import { ClipExportControl } from "@/features/export/ClipExportControl";
import { ExportBar } from "@/features/export/ExportBar";

import { EditorPlayback } from "./EditorPlayback";
import { selectInitialClipId } from "./editor-selection";
import { useEditorClipExport } from "./useEditorClipExport";
import { useEditorClipTrim } from "./useEditorClipTrim";

function clipToListItem(clip: ClipMetadata, index: number): ClipListItem {
  return {
    id: clip.clip_id,
    title: `Clip ${index + 1}`,
    start: clip.start_time,
    end: clip.end_time,
    status: "ready",
  };
}

export interface EditorScreenProps {
  videoId: string;
  initialClipId?: string | null;
}

export function EditorScreen({
  videoId,
  initialClipId = null,
}: EditorScreenProps) {
  const router = useRouter();
  const preferredClipRef = useRef(
    initialClipId && isUuid(initialClipId) ? initialClipId : null,
  );
  const activeClipRef = useRef<string | null>(null);
  const [clips, setClips] = useState<ClipListItem[]>([]);
  const [activeClipId, setActiveClipId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [previewMode, setPreviewMode] = useState<EditorPreviewMode>("clip");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [thumbnailRevisions, setThumbnailRevisions] = useState<
    Record<string, string>
  >({});

  const handleClipTrimSaved = useCallback((clip: ClipMetadata) => {
    setThumbnailRevisions((current) => ({
      ...current,
      [clip.clip_id]: clipThumbnailRevision(
        clip.start_time,
        clip.end_time,
      ),
    }));
  }, []);

  const trimSavedHandlerRef = useRef<(clip: ClipMetadata) => void>(() => {});

  const {
    clipsById,
    sourceDuration,
    trimError,
    saveError,
    isSaving,
    setTrimRange,
    showTrimError,
    replaceClips,
    getTrimRange,
  } = useEditorClipTrim(videoId, {
    onClipTrimSaved: (clip) => trimSavedHandlerRef.current(clip),
  });

  const getTrimRevision = useCallback(
    (clipId: string) => thumbnailRevisions[clipId] ?? null,
    [thumbnailRevisions],
  );

  const getClipExportMeta = useCallback(
    (clipId: string) => {
      const meta = clipsById[clipId];
      const title = clips.find((item) => item.id === clipId)?.title;
      if (!meta || !title) {
        return null;
      }
      return {
        title,
        startTime: meta.start_time,
        endTime: meta.end_time,
      };
    },
    [clipsById, clips],
  );

  const { getExportStatus, exportClip, resetClipExport } = useEditorClipExport({
    videoId,
    getTrimRevision,
    getClipExportMeta,
  });

  const handleClipTrimSavedWithExportReset = useCallback(
    (clip: ClipMetadata) => {
      handleClipTrimSaved(clip);
      resetClipExport(clip.clip_id);
    },
    [handleClipTrimSaved, resetClipExport],
  );

  useEffect(() => {
    trimSavedHandlerRef.current = handleClipTrimSavedWithExportReset;
  }, [handleClipTrimSavedWithExportReset]);
  const [timelineTime, setTimelineTime] = useState(0);
  const seekPlaybackRef = useRef<(time: number) => void>(() => {});

  useEffect(() => {
    activeClipRef.current = activeClipId;
  }, [activeClipId]);

  const syncClipInUrl = useCallback(
    (clipId: string | null) => {
      const params = new URLSearchParams(
        typeof window !== "undefined" ? window.location.search : "",
      );
      if (clipId) {
        params.set("clip", clipId);
      } else {
        params.delete("clip");
      }
      const query = params.toString();
      router.replace(
        `/videos/${videoId}/edit${query ? `?${query}` : ""}`,
        { scroll: false },
      );
    },
    [router, videoId],
  );

  const activateClip = useCallback(
    (clipId: string) => {
      setActiveClipId(clipId);
      setPreviewMode("clip");
      syncClipInUrl(clipId);
      const clip = clipsById[clipId];
      if (clip) {
        setTimelineTime(clip.start_time);
        seekPlaybackRef.current(clip.start_time);
      }
    },
    [syncClipInUrl, clipsById],
  );

  const loadClips = useCallback(async (signal?: AbortSignal) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listVideoClips(videoId, signal);
      replaceClips(response.clips, response.source_duration_seconds);
      setThumbnailRevisions(
        Object.fromEntries(
          response.clips.map((clip) => [
            clip.clip_id,
            clipThumbnailRevision(clip.start_time, clip.end_time),
          ]),
        ),
      );
      const items = response.clips.map(clipToListItem);
      setClips(items);
      const nextId = selectInitialClipId(
        items.map((item) => item.id),
        preferredClipRef.current,
        activeClipRef.current,
      );
      preferredClipRef.current = null;
      setActiveClipId(nextId);
      if (nextId) {
        syncClipInUrl(nextId);
        const clip = response.clips.find((item) => item.clip_id === nextId);
        if (clip) {
          setTimelineTime(clip.start_time);
          seekPlaybackRef.current(clip.start_time);
        }
      }
      setSelectedIds((current) =>
        pruneExportSelection(
          current,
          new Set(items.map((item) => item.id)),
        ),
      );
    } catch (loadError) {
      if (signal?.aborted) {
        return;
      }
      setError(
        loadError instanceof ApiRequestError
          ? loadError.message
          : "We couldn't load your clips. Please try again.",
      );
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }, [videoId, syncClipInUrl, replaceClips]);

  useEffect(() => {
    const controller = new AbortController();
    const task = window.setTimeout(() => {
      void loadClips(controller.signal);
    }, 0);
    return () => {
      window.clearTimeout(task);
      controller.abort();
    };
  }, [loadClips]);

  const activeClipMeta =
    activeClipId !== null ? clipsById[activeClipId] ?? null : null;
  const trimRange = getTrimRange(activeClipId);

  const clipListItems = useMemo((): ClipListItem[] => {
    return clips.map((clip) => {
      const meta = clipsById[clip.id];
      if (!meta) {
        return clip;
      }
      const revision =
        thumbnailRevisions[clip.id] ??
        clipThumbnailRevision(meta.start_time, meta.end_time);
      return {
        ...clip,
        start: meta.start_time,
        end: meta.end_time,
        thumbnailUrl: buildClipThumbnailUrl(videoId, clip.id, revision),
      };
    });
  }, [clips, clipsById, thumbnailRevisions, videoId]);

  const trimmerSegments = useMemo((): TrimmerSegment[] => {
    return clips.map((clip, index) => ({
      id: clip.id,
      start: clipsById[clip.id]?.start_time ?? clip.start,
      end: clipsById[clip.id]?.end_time ?? clip.end,
      label: String(index + 1),
    }));
  }, [clips, clipsById]);

  const handleTrimRangeChange = useCallback(
    (range: { start: number; end: number }) => {
      if (!activeClipId) {
        return;
      }
      setTrimRange(activeClipId, range);
      setClips((current) =>
        current.map((item) =>
          item.id === activeClipId
            ? { ...item, start: range.start, end: range.end }
            : item,
        ),
      );
    },
    [activeClipId, setTrimRange],
  );

  const handleStartFieldChange = useCallback(
    (time: number) => {
      if (!activeClipId || !trimRange) {
        return;
      }
      const result = applyTrimStartChange(trimRange, time, sourceDuration);
      if (!result.ok) {
        showTrimError(result.message);
        return;
      }
      showTrimError(null);
      handleTrimRangeChange(result.range);
    },
    [
      activeClipId,
      trimRange,
      sourceDuration,
      handleTrimRangeChange,
      showTrimError,
    ],
  );

  const handleEndFieldChange = useCallback(
    (time: number) => {
      if (!activeClipId || !trimRange) {
        return;
      }
      const result = applyTrimEndChange(trimRange, time, sourceDuration);
      if (!result.ok) {
        showTrimError(result.message);
        return;
      }
      showTrimError(null);
      handleTrimRangeChange(result.range);
    },
    [
      activeClipId,
      trimRange,
      sourceDuration,
      handleTrimRangeChange,
      showTrimError,
    ],
  );

  const editedDuration =
    trimRange !== null ? trimRange.end - trimRange.start : null;
  const generatedDuration =
    activeClipMeta !== null
      ? activeClipMeta.generated_end_time - activeClipMeta.generated_start_time
      : null;
  const isEdited =
    activeClipMeta !== null &&
    trimRange !== null &&
    (Math.abs(activeClipMeta.generated_start_time - trimRange.start) > 0.05 ||
      Math.abs(activeClipMeta.generated_end_time - trimRange.end) > 0.05);

  return (
    <>
      <AppHeader currentStep="edit" fullWidth />
      <EditorLayout
        clips={
          <ClipList
            clips={clipListItems}
            activeClipId={activeClipId}
            selectedIds={selectedIds}
            onActivate={activateClip}
            onSelectionChange={setSelectedIds}
            renderExport={(clip) => (
              <ClipExportControl
                size="sm"
                clipTitle={clip.title}
                status={getExportStatus(clip.id)}
                onExport={() => exportClip(clip.id)}
                onRetry={() => exportClip(clip.id)}
                disabled={isLoading}
              />
            )}
            isLoading={isLoading}
            error={error}
            onRetry={() => void loadClips()}
            emptyAction={
              <FreshImportLink variant="secondary">
                Import a video
              </FreshImportLink>
            }
          />
        }
        stage={
          <div className="flex flex-col gap-6">
            <EditorPlayback
              videoId={videoId}
              previewMode={previewMode}
              onPreviewModeChange={setPreviewMode}
              activeClipId={activeClipId}
              activeClipLabel={
                clips.find((clip) => clip.id === activeClipId)?.title
              }
              trimRange={trimRange}
              portraitTrimRevision={
                activeClipId
                  ? (thumbnailRevisions[activeClipId] ?? null)
                  : null
              }
              onTimelineTimeChange={setTimelineTime}
              registerSeek={(seek) => {
                seekPlaybackRef.current = seek;
              }}
            />
            {activeClipId && trimRange && sourceDuration > 0 ? (
              <Trimmer
                duration={sourceDuration}
                value={trimRange}
                currentTime={timelineTime}
                segments={trimmerSegments}
                minLength={MIN_CLIP_TRIM_DURATION_SECONDS}
                step={0.1}
                largeStep={1}
                label={
                  clips.find((clip) => clip.id === activeClipId)?.title ??
                  "Clip"
                }
                disabled={isLoading}
                onChange={handleTrimRangeChange}
                onChangeEnd={handleTrimRangeChange}
                onSeek={(time) => {
                  if (previewMode !== "clip") {
                    setPreviewMode("clip");
                  }
                  seekPlaybackRef.current(time);
                }}
              />
            ) : null}
          </div>
        }
        inspector={
          activeClipMeta && trimRange ? (
            <div className="flex flex-col gap-6">
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill tone={isEdited ? "info" : "neutral"}>
                  {isEdited ? "Edited trim" : "Generated trim"}
                </StatusPill>
                {isSaving ? (
                  <StatusPill tone="info" pulse>
                    Saving…
                  </StatusPill>
                ) : null}
              </div>

              <TimeRangeFields
                start={trimRange.start}
                end={trimRange.end}
                currentTime={trimRange.start}
                minLength={MIN_CLIP_TRIM_DURATION_SECONDS}
                error={trimError ?? saveError}
                disabled={isLoading}
                onStartChange={handleStartFieldChange}
                onEndChange={handleEndFieldChange}
              />

              <dl className="grid gap-3 border-t border-border pt-4 text-sm">
                <div>
                  <dt className="text-dense uppercase tracking-wide text-fg-muted">
                    Clip
                  </dt>
                  <dd className="font-medium text-fg">
                    {clips.find((clip) => clip.id === activeClipId)?.title ??
                      "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-dense uppercase tracking-wide text-fg-muted">
                    Generated start
                  </dt>
                  <dd className="font-mono tabular-nums text-fg-muted">
                    {formatTimecode(activeClipMeta.generated_start_time)}
                  </dd>
                </div>
                <div>
                  <dt className="text-dense uppercase tracking-wide text-fg-muted">
                    Generated end
                  </dt>
                  <dd className="font-mono tabular-nums text-fg-muted">
                    {formatTimecode(activeClipMeta.generated_end_time)}
                  </dd>
                </div>
                <div>
                  <dt className="text-dense uppercase tracking-wide text-fg-muted">
                    Edited duration
                  </dt>
                  <dd className="font-mono tabular-nums text-fg">
                    {editedDuration !== null
                      ? formatTimecode(editedDuration)
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-dense uppercase tracking-wide text-fg-muted">
                    Generated duration
                  </dt>
                  <dd className="font-mono tabular-nums text-fg-muted">
                    {generatedDuration !== null
                      ? formatTimecode(generatedDuration)
                      : "—"}
                  </dd>
                </div>
              </dl>

              {activeClipId ? (
                <ClipExportControl
                  clipTitle={
                    clips.find((clip) => clip.id === activeClipId)?.title ??
                    "Clip"
                  }
                  status={getExportStatus(activeClipId)}
                  onExport={() => exportClip(activeClipId)}
                  onRetry={() => exportClip(activeClipId)}
                  disabled={isLoading || isSaving}
                />
              ) : null}
            </div>
          ) : (
            <EmptyState
              size="sm"
              icon={<ListVideo className="size-5" />}
              title="Clip details"
              description="Select a clip to adjust its start and end times."
            />
          )
        }
        footer={
          <>
            <ExportBar
              selectedCount={
                clips.filter((clip) => selectedIds.has(clip.id)).length
              }
              totalCount={clips.length}
              onExportSelected={() => {
                const ordered = clips
                  .filter((clip) => selectedIds.has(clip.id))
                  .map((clip) => clip.id);
                if (ordered.length === 0) {
                  return;
                }
                saveExportSelection(videoId, ordered);
                router.push(buildExportScreenPath(videoId));
              }}
            />
            <div className="border-t border-border bg-surface px-4 py-3 text-center text-sm text-fg-muted">
              Individual exports use the same 9:16 portrait MP4 as the Clip tab.{" "}
              <button
                type="button"
                className="font-medium text-accent underline-offset-2 hover:underline"
                onClick={() => {
                  clearExportSelection(videoId);
                  navigateToFreshImport(router.push);
                }}
              >
                Import another video
              </button>
            </div>
          </>
        }
      />
    </>
  );
}
