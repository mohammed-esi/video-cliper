"use client";

import { useState } from "react";
import { Link2, Upload } from "lucide-react";

import { Card } from "@/components/ui/Card";
import { Tabs, type TabItem } from "@/components/ui/Tabs";

import { FileDropzone } from "./FileDropzone";
import { UploadProgress, type UploadFileInfo } from "./UploadProgress";
import { YoutubeUrlForm } from "./YoutubeUrlForm";

type ImportMethod = "youtube" | "upload";

const METHOD_TABS: ReadonlyArray<TabItem<ImportMethod>> = [
  { id: "youtube", label: "YouTube link", icon: Link2 },
  { id: "upload", label: "Upload file", icon: Upload },
];

export type ImportState =
  | { status: "idle" }
  | { status: "submitting-url" }
  | { status: "url-error"; message: string }
  | { status: "uploading"; file: UploadFileInfo; progress?: number }
  | { status: "upload-error"; file: UploadFileInfo; message: string };

export interface ImportPanelProps {
  state: ImportState;
  maxUploadBytes?: number;
  onSubmitUrl: (url: string) => void;
  onSelectFile: (file: File) => void;
  /** Cancels an in-flight upload, or discards a failed one. */
  onCancelUpload: () => void;
  onRetryUpload: () => void;
}

export function ImportPanel({
  state,
  maxUploadBytes,
  onSubmitUrl,
  onSelectFile,
  onCancelUpload,
  onRetryUpload,
}: ImportPanelProps) {
  const [selectedMethod, setSelectedMethod] = useState<ImportMethod>("youtube");

  const isUploadActive =
    state.status === "uploading" || state.status === "upload-error";
  // An upload in progress or failed keeps its tab in view.
  const method: ImportMethod = isUploadActive ? "upload" : selectedMethod;
  const isBusy =
    state.status === "submitting-url" || state.status === "uploading";

  return (
    <Card className="p-5 shadow-pop sm:p-6">
      <h2 className="sr-only">Import a video</h2>
      <Tabs
        label="Import method"
        items={METHOD_TABS}
        value={method}
        onValueChange={setSelectedMethod}
        disabled={isBusy || isUploadActive}
      >
        {method === "youtube" ? (
          <YoutubeUrlForm
            onSubmit={onSubmitUrl}
            isSubmitting={state.status === "submitting-url"}
            error={state.status === "url-error" ? state.message : null}
          />
        ) : isUploadActive ? (
          <UploadProgress
            file={state.file}
            progress={state.status === "uploading" ? state.progress : undefined}
            error={state.status === "upload-error" ? state.message : null}
            onCancel={onCancelUpload}
            onRetry={onRetryUpload}
          />
        ) : (
          <FileDropzone onFileSelect={onSelectFile} maxBytes={maxUploadBytes} />
        )}
      </Tabs>
    </Card>
  );
}
