"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
  type SyntheticEvent,
} from "react";

import type { MediaStatus } from "@/features/player/MediaStatusMessage";
import {
  clampTimeToTrimWindow,
  shouldStopAtTrimEnd,
  type SourceTimeRange,
} from "@/lib/clips/clip-trim";

import { applyVideoAudioState } from "./video-audio";

export interface EditorPlaybackState {
  videoRef: RefObject<HTMLVideoElement | null>;
  status: MediaStatus;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  isMuted: boolean;
  isLooping: boolean;
  setIsMuted: (muted: boolean) => void;
  setIsLooping: (looping: boolean) => void;
  togglePlayPause: () => void;
  seek: (time: number) => void;
  retryLoad: () => void;
  videoEventHandlers: {
    onLoadedMetadata: (event: SyntheticEvent<HTMLVideoElement>) => void;
    onTimeUpdate: (event: SyntheticEvent<HTMLVideoElement>) => void;
    onPlay: () => void;
    onPause: () => void;
    onEnded: (event: SyntheticEvent<HTMLVideoElement>) => void;
    onError: () => void;
  };
}

export interface UseEditorPlaybackOptions {
  /** When set, playback is constrained to this range on the source timeline. */
  playbackWindow?: SourceTimeRange | null;
}

export function useEditorPlayback(
  src: string | undefined,
  options: UseEditorPlaybackOptions = {},
): EditorPlaybackState {
  const videoRef = useRef<HTMLVideoElement>(null);
  const isMutedRef = useRef(false);
  const playbackWindowRef = useRef(options.playbackWindow ?? null);

  useEffect(() => {
    playbackWindowRef.current = options.playbackWindow ?? null;
  }, [options.playbackWindow]);

  const [status, setStatus] = useState<MediaStatus>(src ? "loading" : "empty");
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isMuted, setIsMutedState] = useState(false);
  const [isLooping, setIsLooping] = useState(false);

  const applyWindowToVideo = useCallback((video: HTMLVideoElement) => {
    const window = playbackWindowRef.current;
    if (!window) {
      return;
    }
    if (video.currentTime < window.start || video.currentTime >= window.end) {
      video.currentTime = window.start;
      setCurrentTime(window.start);
    }
  }, []);

  const setIsMuted = useCallback((muted: boolean) => {
    isMutedRef.current = muted;
    setIsMutedState(muted);
    const video = videoRef.current;
    if (video) {
      applyVideoAudioState(video, { muted });
    }
  }, []);

  useEffect(() => {
    isMutedRef.current = isMuted;
    const video = videoRef.current;
    if (video) {
      applyVideoAudioState(video, { muted: isMuted });
    }
  }, [isMuted, src]);

  useEffect(() => {
    const video = videoRef.current;
    if (video && status === "ready") {
      applyWindowToVideo(video);
    }
  }, [options.playbackWindow, applyWindowToVideo, status]);

  const togglePlayPause = useCallback(() => {
    const video = videoRef.current;
    if (!video || status !== "ready") {
      return;
    }
    if (video.paused) {
      applyWindowToVideo(video);
      applyVideoAudioState(video, { muted: isMutedRef.current });
      void video.play().catch(() => {
        setStatus("error");
        setIsPlaying(false);
      });
    } else {
      video.pause();
    }
  }, [applyWindowToVideo, status]);

  const seek = useCallback(
    (time: number) => {
      const video = videoRef.current;
      if (!video || status === "empty") {
        return;
      }
      const maxDuration = duration || video.duration || 0;
      let target = Math.min(Math.max(time, 0), maxDuration);
      const window = playbackWindowRef.current;
      if (window) {
        target = clampTimeToTrimWindow(target, window);
      }
      video.currentTime = target;
      setCurrentTime(target);
    },
    [duration, status],
  );

  const retryLoad = useCallback(() => {
    const video = videoRef.current;
    if (!video || !src) {
      return;
    }
    setStatus("loading");
    video.load();
  }, [src]);

  const onLoadedMetadata = useCallback(
    (event: SyntheticEvent<HTMLVideoElement>) => {
      const video = event.currentTarget;
      applyVideoAudioState(video, { muted: isMutedRef.current });
      setDuration(Number.isFinite(video.duration) ? video.duration : 0);
      applyWindowToVideo(video);
      setCurrentTime(video.currentTime);
      setStatus("ready");
    },
    [applyWindowToVideo],
  );

  const onTimeUpdate = useCallback((event: SyntheticEvent<HTMLVideoElement>) => {
    const video = event.currentTarget;
    const window = playbackWindowRef.current;
    if (window && shouldStopAtTrimEnd(video.currentTime, window)) {
      video.pause();
      video.currentTime = window.end;
      setCurrentTime(window.end);
      setIsPlaying(false);
      return;
    }
    setCurrentTime(video.currentTime);
  }, []);

  const onPlay = useCallback(() => setIsPlaying(true), []);
  const onPause = useCallback(() => setIsPlaying(false), []);

  const onEnded = useCallback(
    (event: SyntheticEvent<HTMLVideoElement>) => {
      const video = event.currentTarget;
      const window = playbackWindowRef.current;
      if (isLooping) {
        video.currentTime = window?.start ?? 0;
        applyVideoAudioState(video, { muted: isMutedRef.current });
        void video.play().catch(() => setStatus("error"));
        return;
      }
      setIsPlaying(false);
    },
    [isLooping],
  );

  const onError = useCallback(() => {
    setStatus("error");
    setIsPlaying(false);
  }, []);

  return {
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
    videoEventHandlers: {
      onLoadedMetadata,
      onTimeUpdate,
      onPlay,
      onPause,
      onEnded,
      onError,
    },
  };
}
