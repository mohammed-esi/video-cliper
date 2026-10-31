import type { ReactNode } from "react";
import { Scissors } from "lucide-react";

import { cn } from "@/lib/cn";

import { StepIndicator } from "./StepIndicator";

const WORKFLOW_STEPS = [
  { id: "import", label: "Import" },
  { id: "process", label: "Process" },
  { id: "edit", label: "Edit clips" },
  { id: "export", label: "Export" },
] as const;

export type WorkflowStep = (typeof WORKFLOW_STEPS)[number]["id"];

export interface AppHeaderProps {
  currentStep: WorkflowStep;
  /** Right-aligned slot, e.g. the server connection status. */
  status?: ReactNode;
  /** Spans the whole window, to line up with the full-bleed editor. */
  fullWidth?: boolean;
}

export function AppHeader({
  currentStep,
  status,
  fullWidth = false,
}: AppHeaderProps) {
  return (
    <>
      <a
        href="#main"
        className="sr-only z-(--z-toast) rounded-md bg-accent px-4 py-2 text-sm font-medium text-accent-fg focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to main content
      </a>
      <header className="sticky top-0 z-(--z-sticky) h-(--header-height) border-b border-border bg-bg/90 backdrop-blur-md">
        <div
          className={cn(
            "mx-auto flex h-full items-center gap-4 px-4 sm:px-6",
            !fullWidth && "max-w-7xl",
          )}
        >
          <div className="flex shrink-0 items-center gap-2.5">
            <span
              className="flex size-8 items-center justify-center rounded-md bg-accent text-accent-fg"
              aria-hidden
            >
              <Scissors className="size-4" strokeWidth={2.25} />
            </span>
            <span className="text-base font-semibold tracking-tight">
              Video Clipper
            </span>
          </div>

          <div className="flex min-w-0 flex-1 justify-center">
            <StepIndicator steps={WORKFLOW_STEPS} currentStepId={currentStep} />
          </div>

          {status && <div className="hidden shrink-0 sm:block">{status}</div>}
        </div>
      </header>
    </>
  );
}
