"use client";

import { useRef, useState } from "react";

import { ImportPanel, type ImportState } from "./ImportPanel";

// The backend has no import endpoints yet. Until it does, say so plainly
// rather than pretending to start a job.
const NOT_CONNECTED_MESSAGE =
  "Importing isn't connected to the server yet. Please try again later.";

/** Owns the import state; the integration point for the upload and YouTube API calls. */
export function ImportScreen() {
  const [state, setState] = useState<ImportState>({ status: "idle" });
  const fileRef = useRef<File | null>(null);

  function startUpload(file: File) {
    fileRef.current = file;
    setState({
      status: "upload-error",
      file: { name: file.name, size: file.size },
      message: NOT_CONNECTED_MESSAGE,
    });
  }

  return (
    <ImportPanel
      state={state}
      onSubmitUrl={() =>
        setState({ status: "url-error", message: NOT_CONNECTED_MESSAGE })
      }
      onSelectFile={startUpload}
      onCancelUpload={() => {
        fileRef.current = null;
        setState({ status: "idle" });
      }}
      onRetryUpload={() => {
        if (fileRef.current) {
          startUpload(fileRef.current);
        }
      }}
    />
  );
}
