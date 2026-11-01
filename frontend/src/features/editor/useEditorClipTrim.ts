"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiRequestError, updateClipTrim } from "@/lib/api";
import type { ClipMetadata } from "@/lib/api/types";
import {
  normalizeTrimRange,
  type SourceTimeRange,
} from "@/lib/clips/clip-trim";

export interface UseEditorClipTrimResult {
  clipsById: Record<string, ClipMetadata>;
  sourceDuration: number;
  trimError: string | null;
  saveError: string | null;
  isSaving: boolean;
  getTrimRange: (clipId: string | null) => SourceTimeRange | null;
  setTrimRange: (clipId: string, range: SourceTimeRange) => void;
  showTrimError: (message: string | null) => void;
  replaceClips: (
    clips: ClipMetadata[],
    sourceDurationSeconds: number,
  ) => void;
}

export interface UseEditorClipTrimOptions {
  onClipTrimSaved?: (clip: ClipMetadata) => void;
}

export function useEditorClipTrim(
  videoId: string,
  options: UseEditorClipTrimOptions = {},
): UseEditorClipTrimResult {
  const onClipTrimSavedRef = useRef(options.onClipTrimSaved);
  useEffect(() => {
    onClipTrimSavedRef.current = options.onClipTrimSaved;
  }, [options.onClipTrimSaved]);

  const [clipsById, setClipsById] = useState<Record<string, ClipMetadata>>(
    {},
  );
  const [sourceDuration, setSourceDuration] = useState(0);
  const [trimError, setTrimError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const saveTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(
    new Map(),
  );
  useEffect(() => {
    const timers = saveTimersRef.current;
    return () => {
      for (const timer of timers.values()) {
        clearTimeout(timer);
      }
      timers.clear();
    };
  }, []);

  const replaceClips = useCallback(
    (clips: ClipMetadata[], sourceDurationSeconds: number) => {
      setClipsById(Object.fromEntries(clips.map((clip) => [clip.clip_id, clip])));
      setSourceDuration(sourceDurationSeconds);
      setTrimError(null);
      setSaveError(null);
    },
    [],
  );

  const persistTrim = useCallback(
    (clipId: string, range: SourceTimeRange) => {
      const existing = saveTimersRef.current.get(clipId);
      if (existing) {
        clearTimeout(existing);
      }
      const timer = setTimeout(() => {
        saveTimersRef.current.delete(clipId);
        setIsSaving(true);
        setSaveError(null);
        void updateClipTrim(videoId, clipId, {
          start_time: range.start,
          end_time: range.end,
        })
          .then((saved) => {
            setClipsById((current) => ({
              ...current,
              [clipId]: saved,
            }));
            onClipTrimSavedRef.current?.(saved);
          })
          .catch((error: unknown) => {
            setSaveError(
              error instanceof ApiRequestError
                ? error.message
                : "We couldn't save your trim changes. Please try again.",
            );
          })
          .finally(() => {
            setIsSaving(false);
          });
      }, 350);
      saveTimersRef.current.set(clipId, timer);
    },
    [videoId],
  );

  const setTrimRange = useCallback(
    (clipId: string, range: SourceTimeRange) => {
      const validated = normalizeTrimRange(
        range.start,
        range.end,
        sourceDuration,
      );
      if (!validated.ok) {
        setTrimError(validated.message);
        return;
      }
      setTrimError(null);
      const next = validated.range;
      setClipsById((current) => {
        const clip = current[clipId];
        if (!clip) {
          return current;
        }
        return {
          ...current,
          [clipId]: {
            ...clip,
            start_time: next.start,
            end_time: next.end,
            duration: next.end - next.start,
          },
        };
      });
      persistTrim(clipId, next);
    },
    [persistTrim, sourceDuration],
  );

  const getTrimRange = useCallback(
    (clipId: string | null): SourceTimeRange | null => {
      if (!clipId) {
        return null;
      }
      const clip = clipsById[clipId];
      if (!clip) {
        return null;
      }
      return { start: clip.start_time, end: clip.end_time };
    },
    [clipsById],
  );

  const showTrimError = useCallback((message: string | null) => {
    setTrimError(message);
  }, []);

  return {
    clipsById,
    sourceDuration,
    trimError,
    saveError,
    isSaving,
    getTrimRange,
    setTrimRange,
    showTrimError,
    replaceClips,
  };
}
