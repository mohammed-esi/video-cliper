"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { AppHeader } from "@/components/layout/AppHeader";
import { FreshImportLink } from "@/features/import/FreshImportLink";
import { navigateToFreshImport } from "@/features/import/import-navigation";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { ProgressBar } from "@/components/ui/ProgressBar";
import {
  ApiRequestError,
  createGenerateClipsJob,
  listVideoClips,
  userFacingJobError,
} from "@/lib/api";
import { resolveMissingJobRecovery } from "@/lib/processing/missing-job-recovery";
import {
  clearPendingJobId,
  markPendingJobStarting,
  readPendingJobHandoff,
  readPendingJobId,
  savePendingJobId,
} from "@/lib/processing/pending-job";
import {
  isProcessingSource,
  type ProcessingSource,
} from "@/lib/processing/job-view-model";
import {
  readProcessingSessionContext,
  saveProcessingSessionContext,
} from "@/lib/processing/session-context";

import { JobProgress } from "./JobProgress";
import { useJobPolling } from "./useJobPolling";

export interface ProcessingScreenProps {
  videoId: string;
  jobId: string | null;
  source: ProcessingSource;
  videoTitle?: string;
}

type RecoveryUiState =
  | { kind: "checking" }
  | { kind: "clips-ready" }
  | { kind: "needs-action" };

export function ProcessingScreen({
  videoId,
  jobId: initialJobId,
  source,
  videoTitle: initialTitle,
}: ProcessingScreenProps) {
  const router = useRouter();
  const session = useMemo(
    () => readProcessingSessionContext(videoId),
    [videoId],
  );
  const resolvedSource = session?.source ?? source;
  const resolvedTitle =
    initialTitle ?? session?.videoTitle ?? "Your video";

  const [jobId, setJobId] = useState<string | null>(initialJobId);
  const [recoveryUi, setRecoveryUi] = useState<RecoveryUiState>(
    initialJobId ? { kind: "checking" } : { kind: "checking" },
  );
  const [jobCreateError, setJobCreateError] = useState<string | null>(null);
  const [isCreatingJob, setIsCreatingJob] = useState(false);

  useEffect(() => {
    if (initialJobId) {
      return;
    }

    void (async () => {
      const storedJobId = readPendingJobId(videoId);
      let clipCount: number | null = null;

      if (!storedJobId) {
        try {
          const list = await listVideoClips(videoId);
          clipCount = list.clips.length;
        } catch {
          clipCount = null;
        }
      }

      const decision = resolveMissingJobRecovery({
        storedJobId,
        clipCount,
      });

      if (decision.kind === "resume-job") {
        setJobId(decision.jobId);
        setRecoveryUi({ kind: "checking" });
        const params = new URLSearchParams({
          jobId: decision.jobId,
          source: resolvedSource,
        });
        router.replace(
          `/videos/${videoId}/processing?${params.toString()}`,
        );
        return;
      }

      if (decision.kind === "open-editor") {
        setRecoveryUi({ kind: "clips-ready" });
        return;
      }

      setRecoveryUi({ kind: "needs-action" });
    })();
  }, [videoId, initialJobId, router, resolvedSource]);

  const { job, view, isLoading, pollingError, refresh } =
    useJobPolling(jobId);

  const navigateToEditor = useCallback(() => {
    clearPendingJobId(videoId);
    router.push(`/videos/${videoId}/edit`);
  }, [router, videoId]);

  const replaceProcessingUrl = useCallback(
    (nextJobId: string) => {
      const params = new URLSearchParams({
        jobId: nextJobId,
        source: resolvedSource,
      });
      router.replace(
        `/videos/${videoId}/processing?${params.toString()}`,
      );
    },
    [videoId, resolvedSource, router],
  );

  const resumeStoredJob = useCallback(() => {
    const existingJobId = readPendingJobId(videoId);
    if (!existingJobId) {
      return false;
    }
    setJobCreateError(null);
    setJobId(existingJobId);
    replaceProcessingUrl(existingJobId);
    refresh();
    return true;
  }, [videoId, replaceProcessingUrl, refresh]);

  const startNewJob = useCallback(async () => {
    if (readPendingJobHandoff(videoId) === "starting") {
      setJobCreateError(
        "Clip generation is already starting. Wait a moment, then try again.",
      );
      return;
    }

    setIsCreatingJob(true);
    setJobCreateError(null);
    clearPendingJobId(videoId);
    markPendingJobStarting(videoId);

    try {
      const created = await createGenerateClipsJob(videoId);
      savePendingJobId(videoId, created.job_id);
      setJobId(created.job_id);
      replaceProcessingUrl(created.job_id);
      refresh();
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 409) {
        if (resumeStoredJob()) {
          return;
        }
        setJobCreateError(error.message);
        return;
      }
      clearPendingJobId(videoId);
      setJobCreateError(userFacingJobError(error));
    } finally {
      setIsCreatingJob(false);
    }
  }, [videoId, replaceProcessingUrl, refresh, resumeStoredJob]);

  if (!jobId) {
    if (recoveryUi.kind === "checking") {
      return (
        <>
          <AppHeader currentStep="process" />
          <main id="main" className="flex flex-1 justify-center px-4 py-10 sm:px-6">
            <Card className="w-full max-w-lg p-6 shadow-pop sm:p-8">
              <ProgressBar label="Checking processing status…" value={undefined} />
            </Card>
          </main>
        </>
      );
    }

    if (recoveryUi.kind === "clips-ready") {
      return (
        <>
          <AppHeader currentStep="process" />
          <main id="main" className="flex flex-1 justify-center px-4 py-10 sm:px-6">
            <Card className="w-full max-w-lg p-6 shadow-pop sm:p-8">
              <ErrorState
                title="Clips already available"
                message="This video already has generated clips. Open the editor to review them."
                onRetry={navigateToEditor}
                retryLabel="Review clips"
                secondaryAction={
                  <FreshImportLink variant="secondary">
                    Back to import
                  </FreshImportLink>
                }
              />
            </Card>
          </main>
        </>
      );
    }

    return (
      <>
        <AppHeader currentStep="process" />
        <main id="main" className="flex flex-1 justify-center px-4 py-10 sm:px-6">
          <Card className="w-full max-w-lg p-6 shadow-pop sm:p-8">
            <ErrorState
              title="Missing processing job"
              message="We couldn't find a job ID for this video. If processing was already running, open import and return from there, or start clip generation when you're ready."
              onRetry={() => void startNewJob()}
              retryLabel="Start clip generation"
              secondaryAction={
                <FreshImportLink variant="secondary">
                  Back to import
                </FreshImportLink>
              }
            />
            {jobCreateError && (
              <p role="alert" className="mt-4 text-sm text-danger">
                {jobCreateError}
              </p>
            )}
          </Card>
        </main>
      </>
    );
  }

  const blockingError = jobCreateError ?? pollingError;
  const displayError =
    view?.error ??
    (blockingError && !isLoading ? blockingError : null);

  const stage = view?.stage ?? "processing";
  const progress = view?.progress;
  const message = view?.message;

  const showProgressCard = !blockingError || view?.error || job;

  return (
    <>
      <AppHeader currentStep="process" />
      <main id="main" className="flex flex-1 justify-center px-4 py-10 sm:px-6 md:py-14">
        <div className="w-full max-w-lg">
          {showProgressCard ? (
            <JobProgress
              source={resolvedSource}
              pipeline="generate_clips"
              stage={stage}
              progress={progress}
              message={message}
              videoTitle={resolvedTitle}
              error={displayError}
              onRetry={() => {
                if (view?.error || job?.status === "failed") {
                  void startNewJob();
                  return;
                }
                refresh();
              }}
              onStartOver={() => navigateToFreshImport(router.push)}
              onCancel={() => navigateToFreshImport(router.push)}
              cancelLabel="Back to import"
              onContinue={
                job?.status === "completed" ? navigateToEditor : undefined
              }
            />
          ) : (
            <Card className="p-6 shadow-pop sm:p-8">
              <ErrorState
                message={blockingError ?? "Something went wrong."}
                onRetry={() => {
                  if (pollingError) {
                    refresh();
                  } else {
                    void startNewJob();
                  }
                }}
                secondaryAction={
                  <FreshImportLink variant="secondary">
                    Start over
                  </FreshImportLink>
                }
              />
            </Card>
          )}
          {isCreatingJob && (
            <p className="sr-only" aria-live="polite">
              Starting processing…
            </p>
          )}
        </div>
      </main>
    </>
  );
}

export function parseProcessingSearchParams(
  searchParams: Readonly<URLSearchParams>,
): {
  jobId: string | null;
  source: ProcessingSource;
} {
  const jobId = searchParams.get("jobId");
  const sourceParam = searchParams.get("source") ?? "upload";
  const source = isProcessingSource(sourceParam) ? sourceParam : "upload";
  return { jobId, source };
}

/** Persists title/source for refresh, then builds the processing URL. */
export function buildProcessingPath(
  videoId: string,
  jobId: string,
  context: { source: ProcessingSource; videoTitle: string },
): string {
  saveProcessingSessionContext(videoId, context);
  const params = new URLSearchParams({
    jobId,
    source: context.source,
  });
  return `/videos/${videoId}/processing?${params.toString()}`;
}
