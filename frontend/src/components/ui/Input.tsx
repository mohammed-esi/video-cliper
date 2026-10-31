import { useId, type ComponentPropsWithRef, type ReactNode } from "react";
import { CircleAlert } from "lucide-react";

import { cn } from "@/lib/cn";

export interface InputProps extends Omit<ComponentPropsWithRef<"input">, "id"> {
  /** Always visible; placeholders are not labels. */
  label: string;
  hint?: ReactNode;
  /** Shown below the field and announced to screen readers. */
  error?: string | null;
  icon?: ReactNode;
  /** Rendered beside the field, e.g. a related action button. */
  trailing?: ReactNode;
  id?: string;
}

export function Input({
  label,
  hint,
  error,
  icon,
  trailing,
  id,
  className,
  ...rest
}: InputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;
  const describedBy =
    [hint && hintId, error && errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-fg">
        {label}
      </label>
      <div className="flex gap-2">
        <div className="relative flex-1">
          {icon && (
            <span
              className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-fg-muted [&_svg]:size-4"
              aria-hidden
            >
              {icon}
            </span>
          )}
          <input
            id={inputId}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className={cn(
              "h-11 w-full rounded-md border border-border-strong bg-bg px-3 text-base text-fg",
              "placeholder:text-fg-subtle",
              "transition-colors duration-(--dur-fast) ease-out",
              "hover:border-fg-subtle focus-visible:border-accent focus-visible:outline-offset-0",
              "disabled:cursor-not-allowed disabled:opacity-50",
              "aria-invalid:border-danger",
              icon ? "pl-9" : undefined,
              className,
            )}
            {...rest}
          />
        </div>
        {trailing}
      </div>
      {hint && (
        <p id={hintId} className="text-dense text-fg-muted">
          {hint}
        </p>
      )}
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
