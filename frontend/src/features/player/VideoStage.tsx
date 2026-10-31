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
  ref,
  videoProps,
  emptyTitle = "No video loaded",
  emptyDescription,
  errorMessage = "This video couldn't be played.",
  onRetry,
  children,
  className,
}: VideoStageProps) {
  // Fill the stage along whichever side the source touches first (letterbox
  // or pillarbox), so overlay coordinates map 1:1 onto the picture.
  const pictureSize =
    aspectRatio >= STAGE_ASPECT ? { width: "100%" } : { height: "100%" };

  return (
    <div
      data-theme="dark"
      className={cn(
        "@container relative aspect-video w-full overflow-hidden rounded-lg bg-surface-sunken text-fg ring-1 ring-border",
        className,
      )}
    >
      <div className="absolute inset-0 flex items-center justify-center">
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
              className="absolute inset-0 size-full object-fill"
              {...videoProps}
            />
          )}
          {status === "ready" && children}
        </div>
      </div>

      {status !== "ready" && (
        <MediaStatusMessage
          status={status}
          emptyIcon={<Film />}
          emptyTitle={emptyTitle}
          emptyDescription={emptyDescription}
          loadingLabel="Loading video…"
          errorMessage={errorMessage}
          onRetry={onRetry}
        />
      )}
    </div>
  );
}
