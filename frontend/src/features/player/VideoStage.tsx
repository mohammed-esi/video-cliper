import type { ComponentPropsWithoutRef, ReactNode, Ref } from "react";
import { Film } from "lucide-react";

import { cn } from "@/lib/cn";

import { MediaStatusMessage, type MediaStatus } from "./MediaStatusMessage";

const STAGE_ASPECT = 16 / 9;

export interface VideoStageProps {
  status: MediaStatus;
  src?: string;
  poster?: string;
  /** Accessible name for the video, e.g. "Source video". */
  label: string;
  /** Source width ÷ height, so overlays line up with the picture. Defaults to 16:9. */
  aspectRatio?: number;
  /** Outer frame shape: full-width 16:9 stage vs centered 9:16 portrait column. */
  stageLayout?: "landscape" | "portrait";
  /** Attach playback logic (currentTime, timeupdate…) through this ref. */
  ref?: Ref<HTMLVideoElement>;
  /** Extra attributes and media event handlers for the `<video>` element. */
  videoProps?: Omit<
    ComponentPropsWithoutRef<"video">,
    "src" | "poster" | "children" | "className"
  >;
  emptyTitle?: string;
  emptyDescription?: string;
  errorMessage?: string;
  loadingLabel?: string;
  onRetry?: () => void;
  /** Overlays such as CropOverlay. Positioned over the picture; shown only when ready. */
  children?: ReactNode;
  className?: string;
}

/**
 * The 16:9 player surface. Always rendered dark (data-theme="dark") so footage
 * is judged against a neutral frame in either theme.
 */
export function VideoStage({
  status,
  src,
  poster,
  label,
  aspectRatio = STAGE_ASPECT,
  stageLayout = "landscape",
  ref,
  videoProps,
  emptyTitle = "No video loaded",
  emptyDescription,
  errorMessage = "This video couldn't be played.",
  loadingLabel = "Loading video…",
  onRetry,
  children,
  className,
}: VideoStageProps) {
  // Fill the stage along whichever side the source touches first (letterbox
  // or pillarbox), so overlay coordinates map 1:1 onto the picture.
  const pictureSize =
    aspectRatio >= STAGE_ASPECT ? { width: "100%" } : { height: "100%" };

  const videoClassName =
    stageLayout === "portrait"
      ? "absolute inset-0 size-full object-contain"
      : "absolute inset-0 size-full object-fill";

  const pictureFrame = (
    <div
      className="relative max-h-full max-w-full"
      style={{ aspectRatio, ...pictureSize }}
    >
      {(src || poster) && (
        <video
          ref={ref}
          src={src}
          poster={poster}
          preload="metadata"
          playsInline
          aria-label={label}
          className={videoClassName}
          {...videoProps}
        />
      )}
      {status === "ready" && children}
    </div>
  );

  if (stageLayout === "portrait") {
    return (
      <div
        data-theme="dark"
        className={cn(
          "@container flex w-full justify-center rounded-lg bg-surface-sunken text-fg ring-1 ring-border",
          className,
        )}
      >
        <div className="relative mx-auto aspect-[9/16] h-[min(72vh,42rem)] w-auto max-w-full overflow-hidden">
          <div className="absolute inset-0 flex items-center justify-center">
            {pictureFrame}
          </div>
          {status !== "ready" && (
            <MediaStatusMessage
              status={status}
              emptyIcon={<Film />}
              emptyTitle={emptyTitle}
              emptyDescription={emptyDescription}
              loadingLabel={loadingLabel}
              errorMessage={errorMessage}
              onRetry={onRetry}
              compact
            />
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      data-theme="dark"
      className={cn(
        "@container relative aspect-video w-full overflow-hidden rounded-lg bg-surface-sunken text-fg ring-1 ring-border",
        className,
      )}
    >
      <div className="absolute inset-0 flex items-center justify-center">
        {pictureFrame}
      </div>

      {status !== "ready" && (
        <MediaStatusMessage
          status={status}
          emptyIcon={<Film />}
          emptyTitle={emptyTitle}
          emptyDescription={emptyDescription}
          loadingLabel={loadingLabel}
          errorMessage={errorMessage}
          onRetry={onRetry}
        />
      )}
    </div>
  );
}
