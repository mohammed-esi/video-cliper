"use client";

import { useEffect, useRef, useState } from "react";

import {
  UploadAbortError,
  importYoutubeVideo,
  uploadVideo,
  userFacingImportError,
  userFacingUploadError,
} from "@/lib/api";
import { getMaxUploadBytes } from "@/lib/upload-config";

import { ImportPanel, type ImportState } from "./ImportPanel";

/** Owns the import state; wires the existing import UI to the backend APIs. */
export function ImportScreen() {
  const [state, setState] = useState<ImportState>({ status: "idle" });
  const fileRef = useRef<File | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const maxUploadBytes = getMaxUploadBytes();

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  function resetImport() {
    abortRef.current?.abort();
    abortRef.current = null;
    fileRef.current = null;
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
        setState({
          status: "upload-complete",
          file: { name: file.name, size: file.size },
          video,
        });
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
        setState({
          status: "url-import-complete",
          video,
          label: video.original_filename,
        });
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
    />
  );
}
