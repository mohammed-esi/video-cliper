import type { ComponentPropsWithRef, ReactNode } from "react";
import { LoaderCircle } from "lucide-react";

import { cn } from "@/lib/cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-accent text-accent-fg hover:bg-accent-hover",
  secondary:
    "border border-border-strong bg-surface-raised text-fg hover:bg-surface-hover",
  ghost: "text-fg-muted hover:bg-surface-hover hover:text-fg",
  danger: "border border-danger/40 text-danger hover:bg-danger-soft",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-8 gap-1.5 rounded-sm px-3 text-dense [&_svg]:size-4",
  md: "h-10 gap-2 rounded-md px-4 text-sm [&_svg]:size-4",
  lg: "h-12 gap-2 rounded-md px-5 text-base [&_svg]:size-5",
};

/** Shared button look, for elements that must be links (e.g. downloads). */
export function buttonStyles({
  variant = "primary",
  size = "md",
  fullWidth = false,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
} = {}): string {
  return cn(
    "inline-flex shrink-0 items-center justify-center font-medium whitespace-nowrap select-none",
    "transition-colors duration-(--dur-fast) ease-out",
    "disabled:cursor-not-allowed disabled:opacity-50",
    variantClasses[variant],
    sizeClasses[size],
    fullWidth && "w-full",
  );
}

export interface ButtonProps extends ComponentPropsWithRef<"button"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner in place of the icon and blocks further clicks. */
  isLoading?: boolean;
  icon?: ReactNode;
  /** Icon rendered after the label, e.g. a forward arrow. */
  trailingIcon?: ReactNode;
  fullWidth?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
  isLoading = false,
  icon,
  trailingIcon,
  fullWidth = false,
  disabled,
  type = "button",
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined}
      className={cn(buttonStyles({ variant, size, fullWidth }), className)}
      {...rest}
    >
      {isLoading ? <LoaderCircle className="animate-spin" aria-hidden /> : icon}
      {children}
      {!isLoading && trailingIcon}
    </button>
  );
}

export interface ButtonLinkProps extends ComponentPropsWithRef<"a"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: ReactNode;
  fullWidth?: boolean;
}

/** A link styled as a button, e.g. for downloading a finished file. */
export function ButtonLink({
  variant = "primary",
  size = "md",
  icon,
  fullWidth = false,
  className,
  children,
  ...rest
}: ButtonLinkProps) {
  return (
    <a
      className={cn(buttonStyles({ variant, size, fullWidth }), className)}
      {...rest}
    >
      {icon}
      {children}
    </a>
  );
}
