import {
  ArrowRight,
  Check,
  CircleAlert,
  CircleCheck,
  LoaderCircle,
  RotateCcw,
  WandSparkles,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { cn } from "@/lib/cn";

export type JobStage = "importing" | "analyzing" | "processing" | "completed";

/** Matches backend operations shown on the processing screen. */
export type JobProgressPipeline = "default" | "generate_clips";

export interface JobProgressProps {
  /** Decides the wording of the first stage. */
  source: "upload" | "youtube";
  /** When `generate_clips`, hides analysis/subject-tracking steps that do not run yet. */
  pipeline?: JobProgressPipeline;
  stage: JobStage;
  /** Progress within the current stage, 0–1. Omit while unknown. */
  progress?: number;
  /** User-safe status line from the server, e.g. "Detecting faces…". */
  message?: string;
  /** File name or video title, shown under the heading. */
  videoTitle?: string;
  /** When set, the current stage failed with this message. */
  error?: string | null;
  onRetry?: () => void;
  onStartOver?: () => void;
  /** Shown while running; does not cancel backend work. */
  onCancel?: () => void;
  cancelLabel?: string;
  /** Shown when completed: "Review clips". */
  onContinue?: () => void;
  className?: string;
}

type StepState = "done" | "active" | "failed" | "pending";

/** Processing status card: stage checklist, overall progress, and outcome actions. */
export function JobProgress({
  source,
  pipeline = "default",
  stage,
  progress,
  message,
  videoTitle,
  error,
  onRetry,
  onStartOver,
  onCancel,
  cancelLabel = "Back to import",
  onContinue,
  className,
}: JobProgressProps) {
  const importStep = {
    id: "importing",
    label:
      source === "youtube" ? "Downloading from YouTube" : "Uploading video",
    description: "Bringing your video into the editor.",
  } as const;

  const steps =
    pipeline === "generate_clips"
      ? ([
          importStep,
          {
            id: "processing",
            label: "Generating clips",
            description: "Splitting your video into clip files with FFmpeg.",
          },
        ] as const)
      : ([
          importStep,
          {
            id: "analyzing",
            label: "Analyzing video",
            description: "Finding clip boundaries and tracking the speaker.",
          },
          {
            id: "processing",
            label: "Preparing clips",
            description: "Creating a preview for each clip.",
          },
        ] as const);

  const isCompleted = stage === "completed";
  const hasFailed = Boolean(error) && !isCompleted;
  const currentIndex = isCompleted
    ? steps.length
    : steps.findIndex((step) => step.id === stage);
  const stageFraction = Math.min(Math.max(progress ?? 0, 0), 1);
  const overall = isCompleted
    ? 1
    : (currentIndex + stageFraction) / steps.length;

  const stepState = (index: number): StepState =>
    index < currentIndex
      ? "done"
      : index > currentIndex
        ? "pending"
        : hasFailed
          ? "failed"
          : "active";

  const heading = isCompleted
    ? "Your clips are ready"
    : hasFailed
      ? "We couldn't finish preparing your video"
      : "Preparing your clips";

  const announcement = isCompleted
    ? "Your clips are ready."
    : hasFailed
      ? ""
      : `${steps[currentIndex]?.label ?? ""}.`;

  return (
    <Card
      className={cn("flex flex-col gap-6 p-6 shadow-pop sm:p-8", className)}
    >
      <p className="sr-only" aria-live="polite">
        {announcement}
      </p>

      <div className="flex items-start gap-4">
        <span
          className={cn(
            "flex size-12 shrink-0 items-center justify-center rounded-lg [&_svg]:size-6",
            isCompleted
              ? "bg-success-soft text-success"
              : hasFailed
                ? "bg-danger-soft text-danger"
                : "bg-accent-soft text-accent",
          )}
          aria-hidden
        >
          {isCompleted ? (
            <CircleCheck />
          ) : hasFailed ? (
            <CircleAlert />
          ) : (
            <WandSparkles />
          )}
        </span>
        <div className="flex min-w-0 flex-col gap-1">
          <h2 className="text-xl font-semibold tracking-tight">{heading}</h2>
          {videoTitle && (
            <p className="truncate text-sm text-fg-muted" title={videoTitle}>
              {videoTitle}
            </p>
          )}
        </div>
      </div>

      {!hasFailed && (
        <ProgressBar
          label={isCompleted ? "Done" : "Overall progress"}
          // Unknown progress animates instead of sitting at a misleading 0%.
          value={isCompleted || progress !== undefined ? overall : undefined}
          tone={isCompleted ? "success" : "accent"}
        />
      )}

      <ol className="flex flex-col">
        {steps.map((step, index) => {
          const state = stepState(index);
          const isLast = index === steps.length - 1;
          return (
            <li key={step.id} className="relative flex gap-4 pb-5 last:pb-0">
              {!isLast && (
                <span
                  className={cn(
                    "absolute top-8 bottom-1 left-[13px] w-0.5 rounded-full",
                    state === "done" ? "bg-success/50" : "bg-border-strong",
                  )}
                  aria-hidden
                />
              )}
              <StepIcon state={state} number={index + 1} />
              <div className="flex min-w-0 flex-1 flex-col gap-0.5 pt-0.5">
                <p className="flex items-baseline justify-between gap-3">
                  <span
                    className={cn(
                      "text-sm font-medium",
                      state === "pending" ? "text-fg-muted" : "text-fg",
                    )}
                  >
                    {step.label}
                    <span className="sr-only">
                      {state === "done"
                        ? " (done)"
                        : state === "active"
                          ? " (in progress)"
                          : state === "failed"
                            ? " (failed)"
                            : ""}
                    </span>
                  </span>
                  {state === "active" && progress !== undefined && (
                    <span className="font-mono text-dense text-fg-muted tabular-nums">
                      {Math.round(stageFraction * 100)}%
                    </span>
                  )}
                </p>
                <p className="text-dense text-fg-muted">
                  {state === "active" && message ? message : step.description}
                </p>
              </div>
            </li>
          );
        })}
      </ol>

      {hasFailed && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-fg"
        >
          <CircleAlert
            className="mt-0.5 size-4 shrink-0 text-danger"
            aria-hidden
          />
          {error}
        </p>
      )}

      {(hasFailed
        ? onRetry || onStartOver
        : isCompleted
          ? onContinue
          : onCancel) && (
        <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-5">
          {hasFailed && onStartOver && (
            <Button variant="secondary" onClick={onStartOver}>
              Start over
            </Button>
          )}
          {hasFailed && onRetry && (
            <Button icon={<RotateCcw />} onClick={onRetry}>
              Try again
            </Button>
          )}
          {!hasFailed && !isCompleted && onCancel && (
            <Button variant="ghost" icon={<X />} onClick={onCancel}>
              {cancelLabel}
            </Button>
          )}
          {isCompleted && onContinue && (
            <Button trailingIcon={<ArrowRight />} onClick={onContinue}>
              Review clips
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}

function StepIcon({ state, number }: { state: StepState; number: number }) {
  return (
    <span
      className={cn(
        "relative flex size-7 shrink-0 items-center justify-center rounded-full font-mono text-xs font-medium [&_svg]:size-4",
        state === "done" && "bg-success-soft text-success",
        state === "active" && "bg-accent-soft text-accent",
        state === "failed" && "bg-danger-soft text-danger",
        state === "pending" && "border border-border-strong text-fg-muted",
      )}
      aria-hidden
    >
      {state === "done" ? (
        <Check strokeWidth={3} />
      ) : state === "active" ? (
        <LoaderCircle className="animate-spin" />
      ) : state === "failed" ? (
        <X strokeWidth={3} />
      ) : (
        number
      )}
    </span>
  );
}
