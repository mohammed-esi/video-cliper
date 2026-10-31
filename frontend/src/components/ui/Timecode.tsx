import { cn } from "@/lib/cn";
import { formatTimecode } from "@/lib/format";

export interface TimecodeProps {
  seconds: number;
  className?: string;
}

/** A time in mm:ss.s with fixed-width digits, so it doesn't jitter while playing. */
export function Timecode({ seconds, className }: TimecodeProps) {
  return (
    <time
      dateTime={`PT${Math.max(seconds, 0).toFixed(1)}S`}
      className={cn("font-mono tabular-nums", className)}
    >
      {formatTimecode(seconds)}
    </time>
  );
}
