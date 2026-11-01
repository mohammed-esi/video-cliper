"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  UploadAbortError,
  createGenerateClipsJob,
  importYoutubeVideo,
  uploadVideo,
  userFacingImportError,
  userFacingJobError,
  userFacingUploadError,
} from "@/lib/api";
import type { VideoUploadResponse } from "@/lib/api/types";
import {
  buildProcessingPath,
} from "@/features/processing/ProcessingScreen";
import {
  clearPendingJobId,
  markPendingJobStarting,
  readPendingJobHandoff,
  savePendingJobId,
  waitForPendingJobId,
} from "@/lib/processing/pending-job";
import { getMaxUploadBytes } from "@/lib/upload-config";

import { ImportPanel, type ImportState } from "./ImportPanel";

/** Owns the import state; wires the existing import UI to the backend APIs. */
export function ImportScreen() {
  const router = useRouter();
  const [state, setState] = useState<ImportState>({ status: "idle" });
  const fileRef = useRef<File | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const handoffRef = useRef<string | null>(null);
  const maxUploadBytes = getMaxUploadBytes();

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const beginClipGeneration = useCallback(
    (
      video: VideoUploadResponse,
      source: "upload" | "youtube",
      label: string,
    ) => {
      const videoId = video.video_id;
      const handoff = readPendingJobHandoff(videoId);

      if (handoff && handoff !== "starting") {
        router.push(
          buildProcessingPath(videoId, handoff.jobId, {
            source,
            videoTitle: label,
          }),
        );
        return;
      }

      if (handoff === "starting") {
        if (handoffRef.current !== videoId) {
          handoffRef.current = videoId;
          setState({
            status: "starting-processing",
            source,
            video,
            label,
          });
          void waitForPendingJobId(videoId).then((jobId) => {
            if (jobId) {
              router.push(
                buildProcessingPath(videoId, jobId, {
                  source,
                  videoTitle: label,
                }),
              );
              return;
            }
            handoffRef.current = null;
            clearPendingJobId(videoId);
            setState({
              status: "processing-start-error",
              source,
              video,
              label,
              message:
                "Clip generation did not finish starting. Please try again.",
            });
          });
        }
        return;
      }

      if (handoffRef.current === videoId) {
        return;
      }
      handoffRef.current = videoId;
      markPendingJobStarting(videoId);

      setState({
        status: "starting-processing",
        source,
        video,
        label,
      });

      createGenerateClipsJob(videoId)
        .then((job) => {
          savePendingJobId(videoId, job.job_id);
          router.push(
            buildProcessingPath(videoId, job.job_id, {
              source,
              videoTitle: label,
            }),
          );
        })
        .catch((error: unknown) => {
          handoffRef.current = null;
          clearPendingJobId(videoId);
          setState({
            status: "processing-start-error",
            source,
            video,
            label,
            message: userFacingJobError(error),
          });
        });
    },
    [router],
  );

  function resetImport() {
    abortRef.current?.abort();
    abortRef.current = null;
    fileRef.current = null;
    handoffRef.current = null;
    setState({ status: "idle" });
  }

  function startUpload(file: File) {
    fileRef.current = file;
    abortRef.current?.abort();

    const controller = new AbortController();
    abortRef.current = controller;

    setState({
      status: "uploading",
      file: { name: file.name, size: file.size },
      progress: undefined,
    });

    uploadVideo(file, {
      signal: controller.signal,
      onProgress: (progress) => {
        if (controller.signal.aborted) {
          return;
        }
        setState({
          status: "uploading",
          file: { name: file.name, size: file.size },
          progress,
        });
      },
    })
      .then((video) => {
        if (controller.signal.aborted) {
          return;
        }
        beginClipGeneration(video, "upload", file.name);
      })
      .catch((error: unknown) => {
        if (error instanceof UploadAbortError) {
          setState({ status: "idle" });
          return;
        }
        if (controller.signal.aborted) {
          return;
        }
        setState({
          status: "upload-error",
          file: { name: file.name, size: file.size },
          message: userFacingUploadError(error),
        });
      })
      .finally(() => {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      });
  }

  function startYoutubeImport(url: string) {
    if (state.status === "submitting-url") {
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ status: "submitting-url" });

    importYoutubeVideo(url, { signal: controller.signal })
      .then((video) => {
        if (controller.signal.aborted) {
          return;
        }
        beginClipGeneration(
          video,
          "youtube",
          video.original_filename,
        );
      })
      .catch((error: unknown) => {
        if (error instanceof UploadAbortError) {
          setState({ status: "idle" });
          return;
        }
        if (controller.signal.aborted) {
          return;
        }
        const message = userFacingImportError(error);
        setState({
          status: "url-error",
          message: message || "We couldn't import this YouTube video. Try another link.",
        });
      })
      .finally(() => {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      });
  }

  function retryProcessingStart() {
    if (state.status !== "processing-start-error") {
      return;
    }
    clearPendingJobId(state.video.video_id);
    handoffRef.current = null;
    beginClipGeneration(state.video, state.source, state.label);
  }

  return (
    <ImportPanel
      state={state}
      maxUploadBytes={maxUploadBytes}
      onSubmitUrl={startYoutubeImport}
      onSelectFile={startUpload}
      onCancelUpload={resetImport}
      onRetryUpload={() => {
        if (fileRef.current) {
          startUpload(fileRef.current);
        }
      }}
      onResetImport={resetImport}
      onRetryProcessingStart={retryProcessingStart}
    />
  );
}
