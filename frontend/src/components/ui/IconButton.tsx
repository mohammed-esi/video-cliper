import type { ComponentPropsWithRef, ReactNode } from "react";

import { cn } from "@/lib/cn";

type IconButtonVariant = "primary" | "secondary" | "ghost";
type IconButtonSize = "sm" | "md" | "lg";

const variantClasses: Record<IconButtonVariant, string> = {
  primary: "bg-accent text-accent-fg hover:bg-accent-hover",
  secondary:
    "border border-border-strong bg-surface-raised text-fg hover:bg-surface-hover",
  ghost: "text-fg-muted hover:bg-surface-hover hover:text-fg",
};

const sizeClasses: Record<IconButtonSize, string> = {
  sm: "size-8 rounded-sm [&_svg]:size-4",
  md: "size-10 rounded-md [&_svg]:size-5",
  lg: "size-12 rounded-full [&_svg]:size-6",
};

export interface IconButtonProps extends Omit<
  ComponentPropsWithRef<"button">,
  "children"
> {
  /** Accessible name, also shown as a native tooltip. */
  label: string;
  icon: ReactNode;
  variant?: IconButtonVariant;
  size?: IconButtonSize;
  /** Makes this a toggle button (aria-pressed) and highlights the on state. */
  pressed?: boolean;
}

export function IconButton({
  label,
  icon,
  variant = "ghost",
  size = "md",
  pressed,
  type = "button",
  className,
  ...rest
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      className={cn(
        "inline-flex shrink-0 items-center justify-center",
        "transition-colors duration-(--dur-fast) ease-out",
        "disabled:cursor-not-allowed disabled:opacity-50",
        pressed
          ? "bg-accent-soft text-accent hover:bg-accent-soft"
          : variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      {...rest}
    >
      <span aria-hidden className="contents">
        {icon}
      </span>
    </button>
  );
}
