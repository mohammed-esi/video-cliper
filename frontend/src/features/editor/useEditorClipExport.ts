"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { ClipExportStatus } from "@/features/export/ClipExportControl";
import { ApiRequestError } from "@/lib/api/errors";
import { buildPortraitDownloadUrl } from "@/lib/api/portrait";
import { exportTrimChanged, triggerPortraitDownload } from "@/lib/clips/clip-export";
import { ensurePortraitReady } from "@/lib/clips/ensure-portrait-ready";

export interface UseEditorClipExportOptions {
  videoId: string;
  getTrimRevision: (clipId: string) => string | null;
  getClipExportMeta: (
    clipId: string,
  ) => { title: string; startTime: number; endTime: number } | null;
}

export interface UseEditorClipExportResult {
  getExportStatus: (clipId: string) => ClipExportStatus;
  exportClip: (clipId: string) => void;
  resetClipExport: (clipId: string) => void;
}

const idleStatus: ClipExportStatus = { state: "idle" };

export function useEditorClipExport(
  options: UseEditorClipExportOptions,
): UseEditorClipExportResult {
  const { videoId, getTrimRevision, getClipExportMeta } = options;
  const getTrimRevisionRef = useRef(getTrimRevision);
  const getClipExportMetaRef = useRef(getClipExportMeta);

  useEffect(() => {
    getTrimRevisionRef.current = getTrimRevision;
  }, [getTrimRevision]);

  useEffect(() => {
    getClipExportMetaRef.current = getClipExportMeta;
  }, [getClipExportMeta]);

  const [statusByClip, setStatusByClip] = useState<
    Record<string, ClipExportStatus>
  >({});
  const inFlightRef = useRef<Map<string, string>>(new Map());

  const resetClipExport = useCallback((clipId: string) => {
    setStatusByClip((current) => {
      if (!(clipId in current)) {
        return current;
      }
      const next = { ...current };
      delete next[clipId];
      return next;
    });
    inFlightRef.current.delete(clipId);
  }, []);

  const getExportStatus = useCallback(
    (clipId: string): ClipExportStatus => {
      return statusByClip[clipId] ?? idleStatus;
    },
    [statusByClip],
  );

  const exportClip = useCallback(
    (clipId: string) => {
      const revision = getTrimRevisionRef.current(clipId);
      const meta = getClipExportMetaRef.current(clipId);
      if (!revision || !meta) {
        return;
      }

      if (inFlightRef.current.get(clipId) === revision) {
        return;
      }

      inFlightRef.current.set(clipId, revision);
      setStatusByClip((current) => ({
        ...current,
        [clipId]: { state: "rendering" },
      }));

      const abortController = new AbortController();
      const expectedRevision = revision;
      void (async () => {
        try {
          await ensurePortraitReady({
            videoId,
            clipId,
            trimRevision: expectedRevision,
            signal: abortController.signal,
          });

          if (inFlightRef.current.get(clipId) !== expectedRevision) {
            return;
          }

          const currentRevision = getTrimRevisionRef.current(clipId);
          if (exportTrimChanged(expectedRevision, currentRevision)) {
            throw new ApiRequestError(
              "This clip's trim changed during export. Please try again.",
            );
          }

          const downloadUrl = buildPortraitDownloadUrl(
            videoId,
            clipId,
            expectedRevision,
          );
          triggerPortraitDownload(downloadUrl);

          if (inFlightRef.current.get(clipId) === expectedRevision) {
            inFlightRef.current.delete(clipId);
            setStatusByClip((current) => ({
              ...current,
              [clipId]: idleStatus,
            }));
          }
        } catch (error) {
          if (inFlightRef.current.get(clipId) !== expectedRevision) {
            return;
          }
          inFlightRef.current.delete(clipId);
          const message =
            error instanceof ApiRequestError
              ? error.message
              : "We couldn't export this clip. Please try again.";
          setStatusByClip((current) => ({
            ...current,
            [clipId]: { state: "failed", message },
          }));
        }
      })();
    },
    [videoId],
  );

  return { getExportStatus, exportClip, resetClipExport };
}
