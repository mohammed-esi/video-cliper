import type { ComponentPropsWithRef } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, ...rest }: ComponentPropsWithRef<"div">) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-surface text-fg",
        className,
      )}
      {...rest}
    />
  );
}
