"use client";

import { useId, useRef, useState, type DragEvent } from "react";
import { CircleAlert, CloudUpload } from "lucide-react";

import { cn } from "@/lib/cn";
import { formatBytes } from "@/lib/format";
import {
  ACCEPTED_VIDEO_EXTENSIONS,
  getVideoFileError,
} from "@/lib/import-validation";

export interface FileDropzoneProps {
  /** Called with a file that passed the client-side checks. */
  onFileSelect: (file: File) => void;
  maxBytes?: number;
  disabled?: boolean;
}

export function FileDropzone({
  onFileSelect,
  maxBytes,
  disabled = false,
}: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const hintId = useId();
  const errorId = useId();
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function selectFile(file: File) {
    const fileError = getVideoFileError(file, maxBytes);
    setError(fileError);
    if (!fileError) {
      onFileSelect(file);
    }
  }

  function handleDragOver(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    if (!disabled) {
      setIsDragging(true);
      event.dataTransfer.dropEffect = "copy";
    }
  }

  function handleDragLeave(event: DragEvent<HTMLButtonElement>) {
    // Ignore leave events fired when the pointer moves onto a child element.
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setIsDragging(false);
    }
  }

  function handleDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setIsDragging(false);
    if (disabled) {
      return;
    }

    const files = event.dataTransfer.files;
    if (files.length > 1) {
      setError("Drop one video at a time.");
      return;
    }
    if (files.length === 1) {
      selectFile(files[0]);
    }
  }

  const formats = ACCEPTED_VIDEO_EXTENSIONS.map((extension) =>
    extension.slice(1).toUpperCase(),
  ).join(", ");

  return (
    <div className="flex flex-col gap-2">
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        aria-describedby={error ? `${hintId} ${errorId}` : hintId}
        className={cn(
          "group flex min-h-60 w-full flex-col items-center justify-center gap-4 rounded-lg border-2 border-dashed px-6 py-8 text-center",
          "transition-colors duration-(--dur-base) ease-out",
          "disabled:cursor-not-allowed disabled:opacity-50",
          isDragging
            ? "border-accent bg-accent-soft"
            : error
              ? "border-danger/50 bg-bg"
              : "border-border-strong bg-bg hover:border-fg-subtle hover:bg-surface-raised",
        )}
      >
        <span
          className={cn(
            "flex size-12 items-center justify-center rounded-full transition-transform duration-(--dur-base) ease-out",
            isDragging
              ? "scale-110 bg-accent text-accent-fg"
              : "bg-surface-raised text-fg-muted group-hover:text-fg",
          )}
          aria-hidden
        >
          <CloudUpload className="size-6" />
        </span>
        <span className="flex flex-col gap-1">
          <span className="text-base font-medium text-fg">
            {isDragging ? "Drop to upload" : "Drag and drop a video here"}
          </span>
          <span className="text-sm text-fg-muted">
            or{" "}
            <span className="font-medium text-accent">browse your files</span>
          </span>
        </span>
        <span id={hintId} className="text-dense text-fg-muted">
          {formats}
          {maxBytes !== undefined && ` · up to ${formatBytes(maxBytes)}`}
        </span>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_VIDEO_EXTENSIONS.join(",")}
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          // Reset so choosing the same file again still fires a change.
          event.target.value = "";
          if (file) {
            selectFile(file);
          }
        }}
      />

      {error && (
        <p
          id={errorId}
          role="alert"
          className="flex items-start gap-1.5 text-dense text-danger"
        >
          <CircleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {error}
        </p>
      )}
    </div>
  );
}
