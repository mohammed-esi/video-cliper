import { cn } from "@/lib/cn";

/** A rectangle in fractions (0–1) of the picture's width and height. */
export interface CropRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CropOverlayProps {
  /** Where the vertical frame sits. Update it as playback moves to follow the subject. */
  crop: CropRect;
  label?: string;
  /** Rule-of-thirds guides inside the crop window. */
  showGuides?: boolean;
  /**
   * Eases between positions. Turn off when updating every frame, so the
   * window tracks the given coordinates exactly.
   */
  animate?: boolean;
  className?: string;
}

const clamp01 = (value: number) => Math.min(Math.max(value, 0), 1);

/** Dims the picture outside the crop window. Place inside VideoStage. */
export function CropOverlay({
  crop,
  label = "9:16",
  showGuides = true,
  animate = true,
  className,
}: CropOverlayProps) {
  const width = clamp01(crop.width) || 1;
  const height = clamp01(crop.height) || 1;
  const x = Math.min(clamp01(crop.x), 1 - width);
  const y = Math.min(clamp01(crop.y), 1 - height);

  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden",
        className,
      )}
    >
      <div
        className={cn(
          "absolute top-0 left-0 outline-2 outline-accent",
          animate && "transition-transform duration-(--dur-base) ease-out",
        )}
        style={{
          width: `${width * 100}%`,
          height: `${height * 100}%`,
          // Translate is relative to the window's own size, so divide back out.
          transform: `translate(${(x / width) * 100}%, ${(y / height) * 100}%)`,
          // One oversized shadow dims everything outside the window.
          boxShadow: "0 0 0 100vmax var(--crop-scrim)",
        }}
      >
        {showGuides && (
          <>
            <span className="absolute inset-y-0 left-1/3 w-px bg-white/20" />
            <span className="absolute inset-y-0 left-2/3 w-px bg-white/20" />
            <span className="absolute inset-x-0 top-1/3 h-px bg-white/20" />
            <span className="absolute inset-x-0 top-2/3 h-px bg-white/20" />
          </>
        )}
        <span className="absolute top-2 left-2 rounded-sm bg-accent px-1.5 py-0.5 font-mono text-[11px] leading-none font-medium text-accent-fg">
          {label}
        </span>
      </div>
    </div>
  );
}
