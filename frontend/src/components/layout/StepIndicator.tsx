import { Fragment } from "react";
import { Check } from "lucide-react";

import { cn } from "@/lib/cn";

export interface Step {
  id: string;
  label: string;
}

export interface StepIndicatorProps {
  steps: ReadonlyArray<Step>;
  currentStepId: string;
}

export function StepIndicator({ steps, currentStepId }: StepIndicatorProps) {
  const currentIndex = steps.findIndex((step) => step.id === currentStepId);

  return (
    <nav aria-label="Workflow progress">
      <ol className="flex items-center gap-2">
        {steps.map((step, index) => {
          const isDone = index < currentIndex;
          const isCurrent = index === currentIndex;

          return (
            <Fragment key={step.id}>
              {index > 0 && (
                <li
                  role="presentation"
                  aria-hidden
                  className={cn(
                    "h-px w-4 lg:w-8",
                    isDone || isCurrent ? "bg-accent/60" : "bg-border-strong",
                  )}
                />
              )}
              <li
                aria-current={isCurrent ? "step" : undefined}
                className="flex items-center gap-2"
              >
                <span
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-full font-mono text-xs font-medium",
                    isDone && "bg-accent-soft text-accent",
                    isCurrent && "bg-accent text-accent-fg",
                    !isDone &&
                      !isCurrent &&
                      "border border-border-strong text-fg-muted",
                  )}
                  aria-hidden
                >
                  {isDone ? (
                    <Check className="size-3.5" strokeWidth={3} />
                  ) : (
                    index + 1
                  )}
                </span>
                <span
                  className={cn(
                    "text-dense whitespace-nowrap",
                    isCurrent ? "font-medium text-fg" : "text-fg-muted",
                    // Below lg only the current step keeps its label.
                    !isCurrent && "sr-only lg:not-sr-only",
                  )}
                >
                  {step.label}
                  {isDone && <span className="sr-only"> (done)</span>}
                </span>
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
