"use client";

import { useCallback, useEffect, type SyntheticEvent } from "react";
import { Film, Video } from "lucide-react";

import { StatusPill } from "@/components/ui/StatusPill";
import { Tabs, type TabItem } from "@/components/ui/Tabs";
import { PlayerControls } from "@/features/player/PlayerControls";
import { VideoStage } from "@/features/player/VideoStage";
import type { MediaStatus } from "@/features/player/MediaStatusMessage";
import { buildSourceStreamUrl } from "@/lib/api/media-urls";
import type { EditorPreviewMode } from "@/lib/api/media-stream-paths";
import type { SourceTimeRange } from "@/lib/clips/clip-trim";

import {
  mapControlsSeekTarget,
  resolvePlayerControlsTimes,
  sourceTimelineTimeFromVideo,
} from "./editor-playback-time";
import { useEditorPlayback } from "./useEditorPlayback";
import { useEditorPortraitPreview } from "./useEditorPortraitPreview";

const PREVIEW_TABS: ReadonlyArray<TabItem<EditorPreviewMode>> = [
  { id: "clip", label: "Clip", icon: Film },
  { id: "source", label: "Original", icon: Video },
];

const PORTRAIT_ASPECT = 9 / 16;
const SOURCE_ASPECT = 16 / 9;

export interface EditorPlaybackProps {
  videoId: string;
  previewMode: EditorPreviewMode;
  onPreviewModeChange: (mode: EditorPreviewMode) => void;
  activeClipId: string | null;
  activeClipLabel?: string;
  trimRange: SourceTimeRange | null;
  /** Revision from saved trim boundaries (not live drag). */
  portraitTrimRevision: string | null;
  onTimelineTimeChange?: (seconds: number) => void;
  registerSeek?: (seek: (time: number) => void) => void;
}

interface EditorPlaybackPanelProps {
  streamUrl: string | undefined;
  forceEmpty: boolean;
  previewLabel: string;
  loadingLabel: string;
  emptyTitle: string;
  previewMode: EditorPreviewMode;
  aspectRatio: number;
  trimRange: SourceTimeRange | null;
  portraitPreviewActive: boolean;
  portraitErrorMessage: string | null;
  onPortraitRetry?: () => void;
  onPortraitPlaybackReady?: () => void;
  onTimelineTimeChange?: (seconds: number) => void;
  registerSeek?: (seek: (time: number) => void) => void;
}

function EditorPlaybackPanel({
  streamUrl,
  forceEmpty,
  previewLabel,
  loadingLabel,
  emptyTitle,
  previewMode,
  aspectRatio,
  trimRange,
  portraitPreviewActive,
  portraitErrorMessage,
  onPortraitRetry,
  onPortraitPlaybackReady,
  onTimelineTimeChange,
  registerSeek,
}: EditorPlaybackPanelProps) {
  const {
    videoRef,
    status,
    isPlaying,
    currentTime,
    duration,
    isMuted,
    isLooping,
    setIsMuted,
    setIsLooping,
    togglePlayPause,
    seek,
    retryLoad,
    videoEventHandlers,
  } = useEditorPlayback(streamUrl, { playbackWindow: null });

  const seekSourceTimeline = useCallback(
    (sourceTime: number) => {
      if (portraitPreviewActive && trimRange) {
        seek(Math.max(0, sourceTime - trimRange.start));
        return;
      }
      seek(sourceTime);
    },
    [portraitPreviewActive, seek, trimRange],
  );

  const handleControlsSeek = useCallback(
    (seekBarTime: number) => {
      const target = mapControlsSeekTarget({
        portraitPreviewActive,
        trimRange,
        seekBarTime,
      });
      seek(target);
    },
    [portraitPreviewActive, seek, trimRange],
  );

  useEffect(() => {
    registerSeek?.(seekSourceTimeline);
  }, [registerSeek, seekSourceTimeline]);

  useEffect(() => {
    onTimelineTimeChange?.(
      sourceTimelineTimeFromVideo({
        portraitPreviewActive,
        videoLocalTime: currentTime,
        trimRange,
      }),
    );
  }, [currentTime, onTimelineTimeChange, portraitPreviewActive, trimRange]);

  const controlsTimes = resolvePlayerControlsTimes({
    portraitPreviewActive,
    videoLocalTime: currentTime,
    videoDuration: duration,
    trimRange,
  });

  const onLoadedMetadata = useCallback(
    (event: SyntheticEvent<HTMLVideoElement>) => {
      videoEventHandlers.onLoadedMetadata(event);
      if (portraitPreviewActive) {
        onPortraitPlaybackReady?.();
      }
    },
    [
      onPortraitPlaybackReady,
      portraitPreviewActive,
      videoEventHandlers,
    ],
  );

  let resolvedStatus: MediaStatus = forceEmpty ? "empty" : status;
  if (!forceEmpty && portraitErrorMessage) {
    resolvedStatus = "error";
  } else if (
    !forceEmpty &&
    portraitPreviewActive &&
    !streamUrl &&
    resolvedStatus !== "empty"
  ) {
    resolvedStatus = "loading";
  }

  const showPortraitLoading =
    portraitPreviewActive && !portraitErrorMessage && !streamUrl;

  return (
    <div className="flex flex-col gap-4">
      <StatusPill
        tone={resolvedStatus === "error" ? "danger" : "info"}
        pulse={resolvedStatus === "loading" || showPortraitLoading}
      >
        {previewLabel}
      </StatusPill>

      <VideoStage
        ref={videoRef}
        status={resolvedStatus}
        src={streamUrl}
        label={previewLabel}
        aspectRatio={aspectRatio}
        stageLayout={previewMode === "clip" ? "portrait" : "landscape"}
        emptyTitle={emptyTitle}
        emptyDescription={
          previewMode === "clip"
            ? "Choose a clip from the list to watch it here."
            : undefined
        }
        loadingLabel={loadingLabel}
        errorMessage={
          portraitErrorMessage ??
          "This video couldn't be played. Check that the backend is running and try again."
        }
        onRetry={portraitErrorMessage ? onPortraitRetry : retryLoad}
        videoProps={{
          ...videoEventHandlers,
          onLoadedMetadata,
          ...(isMuted ? { muted: true } : {}),
        }}
      />

      <PlayerControls
        isPlaying={isPlaying}
        currentTime={controlsTimes.currentTime}
        duration={controlsTimes.duration}
        isMuted={isMuted}
        isLooping={isLooping}
        onPlayPause={togglePlayPause}
        onSeek={handleControlsSeek}
        onMutedChange={setIsMuted}
        onLoopingChange={setIsLooping}
        disabled={resolvedStatus !== "ready"}
      />
    </div>
  );
}

export function EditorPlayback({
  videoId,
  previewMode,
  onPreviewModeChange,
  activeClipId,
  activeClipLabel,
  trimRange,
  portraitTrimRevision,
  onTimelineTimeChange,
  registerSeek,
}: EditorPlaybackProps) {
  const sourceStreamUrl = buildSourceStreamUrl(videoId);

  const portraitPreview = useEditorPortraitPreview({
    videoId,
    clipId: activeClipId,
    trimRevision: portraitTrimRevision,
    enabled: previewMode === "clip" && Boolean(activeClipId),
  });

  const portraitPreviewActive =
    previewMode === "clip" && Boolean(activeClipId);

  const streamUrl =
    previewMode === "source" ? sourceStreamUrl : portraitPreview.streamUrl;

  const aspectRatio =
    previewMode === "clip" ? PORTRAIT_ASPECT : SOURCE_ASPECT;

  const clipPreviewLabel =
    previewMode === "clip" && activeClipLabel
      ? portraitPreview.phase === "ready" ||
          portraitPreview.phase === "loading"
        ? `Preview: ${activeClipLabel} (9:16 portrait)`
        : portraitPreview.statusLabel
      : previewMode === "source"
        ? "Original source video"
        : portraitPreview.statusLabel;

  const loadingLabel = portraitPreview.statusLabel;

  const forceEmpty = previewMode === "clip" && !activeClipId;

  const emptyTitle =
    previewMode === "clip" ? "No clip selected" : "Original video unavailable";

  const panelKey = [
    previewMode,
    streamUrl ?? "no-stream",
    portraitTrimRevision ?? "no-revision",
    activeClipId ?? "no-clip",
  ].join(":");

  return (
    <Tabs
      label="Preview source"
      items={PREVIEW_TABS}
      value={previewMode}
      onValueChange={onPreviewModeChange}
    >
      <EditorPlaybackPanel
        key={panelKey}
        streamUrl={streamUrl}
        forceEmpty={forceEmpty}
        previewLabel={clipPreviewLabel}
        loadingLabel={loadingLabel}
        emptyTitle={emptyTitle}
        previewMode={previewMode}
        aspectRatio={aspectRatio}
        trimRange={trimRange}
        portraitPreviewActive={portraitPreviewActive}
        portraitErrorMessage={portraitPreview.errorMessage}
        onPortraitRetry={portraitPreview.retry}
        onPortraitPlaybackReady={portraitPreview.markPlaybackReady}
        onTimelineTimeChange={onTimelineTimeChange}
        registerSeek={registerSeek}
      />
    </Tabs>
  );
}
