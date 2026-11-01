"use client";

import { useState } from "react";
import { CheckCircle2, Link2, Upload } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusPill } from "@/components/ui/StatusPill";
import { Tabs, type TabItem } from "@/components/ui/Tabs";
import type { VideoUploadResponse } from "@/lib/api";
import { formatTimecode } from "@/lib/format";

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
  | { status: "upload-error"; file: UploadFileInfo; message: string }
  | {
      status: "upload-complete";
      file: UploadFileInfo;
      video: VideoUploadResponse;
    }
  | {
      status: "url-import-complete";
      video: VideoUploadResponse;
      label: string;
    };

export interface ImportPanelProps {
  state: ImportState;
  maxUploadBytes?: number;
  onSubmitUrl: (url: string) => void;
  onSelectFile: (file: File) => void;
  /** Cancels an in-flight upload, or discards a failed one. */
  onCancelUpload: () => void;
  onRetryUpload: () => void;
  /** Clears a completed or failed import and returns to the idle form. */
  onResetImport: () => void;
}

function ImportCompletePanel({
  label,
  video,
  resetLabel,
  onReset,
}: {
  label: string;
  video: VideoUploadResponse;
  resetLabel: string;
  onReset: () => void;
}) {
  return (
    <div className="flex flex-col gap-5 rounded-lg border border-success/30 bg-bg p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span
            className="flex size-10 shrink-0 items-center justify-center rounded-md bg-success-soft text-success"
            aria-hidden
          >
            <CheckCircle2 className="size-5" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-fg" title={label}>
              {label}
            </p>
            <StatusPill tone="success" className="mt-2">
              Video ready
            </StatusPill>
          </div>
        </div>
      </div>

      <dl className="grid gap-2 text-sm text-fg-muted sm:grid-cols-2">
        <div>
          <dt className="text-dense uppercase tracking-wide">Duration</dt>
          <dd className="font-mono tabular-nums text-fg">
            {formatTimecode(video.duration_seconds)}
          </dd>
        </div>
        <div>
          <dt className="text-dense uppercase tracking-wide">Resolution</dt>
          <dd className="font-mono tabular-nums text-fg">
            {video.width}×{video.height}
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-dense uppercase tracking-wide">Video ID</dt>
          <dd className="truncate font-mono text-dense text-fg" title={video.video_id}>
            {video.video_id}
          </dd>
        </div>
      </dl>

      <Button variant="secondary" onClick={onReset}>
        {resetLabel}
      </Button>
    </div>
  );
}

export function ImportPanel({
  state,
  maxUploadBytes,
  onSubmitUrl,
  onSelectFile,
  onCancelUpload,
  onRetryUpload,
  onResetImport,
}: ImportPanelProps) {
  const [selectedMethod, setSelectedMethod] = useState<ImportMethod>("youtube");

  const isUploadFlow =
    state.status === "uploading" ||
    state.status === "upload-error" ||
    state.status === "upload-complete";
  const isYoutubeFlow =
    state.status === "submitting-url" ||
    state.status === "url-error" ||
    state.status === "url-import-complete";
  const method: ImportMethod = isUploadFlow
    ? "upload"
    : isYoutubeFlow
      ? "youtube"
      : selectedMethod;
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
        disabled={isBusy || isUploadFlow || isYoutubeFlow}
      >
        {method === "youtube" ? (
          state.status === "url-import-complete" ? (
            <ImportCompletePanel
              label={state.label}
              video={state.video}
              resetLabel="Import another video"
              onReset={onResetImport}
            />
          ) : (
            <YoutubeUrlForm
              onSubmit={onSubmitUrl}
              isSubmitting={state.status === "submitting-url"}
              error={state.status === "url-error" ? state.message : null}
            />
          )
        ) : state.status === "upload-complete" ? (
          <ImportCompletePanel
            label={state.file.name}
            video={state.video}
            resetLabel="Upload another file"
            onReset={onResetImport}
          />
        ) : state.status === "uploading" || state.status === "upload-error" ? (
          <UploadProgress
            file={state.file}
            progress={state.status === "uploading" ? state.progress : undefined}
            error={state.status === "upload-error" ? state.message : null}
            onCancel={onCancelUpload}
            onRetry={onRetryUpload}
          />
        ) : (
          <FileDropzone
            onFileSelect={onSelectFile}
            maxBytes={maxUploadBytes}
            disabled={isBusy}
          />
        )}
      </Tabs>
    </Card>
  );
}
