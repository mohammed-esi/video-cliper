import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description?: ReactNode;
  /** Usually one Button that moves the person forward. */
  action?: ReactNode;
  /** "sm" fits narrow panels such as the clip list. */
  size?: "sm" | "md";
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  size = "md",
  className,
}: EmptyStateProps) {
  const isSmall = size === "sm";

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center",
        isSmall ? "gap-2 px-4 py-8" : "gap-3 px-6 py-12",
        className,
      )}
    >
      <span
        className={cn(
          "mb-1 flex items-center justify-center rounded-full border border-border bg-surface-raised text-fg-muted",
          isSmall ? "size-10 [&_svg]:size-5" : "size-12 [&_svg]:size-6",
        )}
        aria-hidden
      >
        {icon}
      </span>
      <p
        className={cn("font-medium text-fg", isSmall ? "text-sm" : "text-base")}
      >
        {title}
      </p>
      {description && (
        <p
          className={cn(
            "max-w-sm text-fg-muted",
            isSmall ? "text-dense" : "text-sm",
          )}
        >
          {description}
        </p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
