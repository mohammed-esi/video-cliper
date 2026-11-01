"use client";

import { useParams, useSearchParams } from "next/navigation";

import { AppHeader } from "@/components/layout/AppHeader";
import { Card } from "@/components/ui/Card";
import { ErrorState } from "@/components/ui/ErrorState";
import { FreshImportLink } from "@/features/import/FreshImportLink";
import {
  ProcessingScreen,
  parseProcessingSearchParams,
} from "@/features/processing/ProcessingScreen";
import { isUuid } from "@/lib/ids";

function InvalidRouteState({ message }: { message: string }) {
  return (
    <>
      <AppHeader currentStep="process" />
      <main id="main" className="flex flex-1 justify-center px-4 py-10 sm:px-6">
        <Card className="w-full max-w-lg p-6 shadow-pop sm:p-8">
          <ErrorState
            title="Invalid link"
            message={message}
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

export function ProcessingRouteLoader() {
  const params = useParams<{ videoId: string }>();
  const searchParams = useSearchParams();
  const videoId = params.videoId;

  if (!videoId || !isUuid(videoId)) {
    return (
      <InvalidRouteState message="This processing link is not valid. Return to import and start again." />
    );
  }

  const { jobId, source } = parseProcessingSearchParams(searchParams);
  if (jobId && !isUuid(jobId)) {
    return (
      <InvalidRouteState message="The job ID in this link is not valid." />
    );
  }

  return (
    <ProcessingScreen
      videoId={videoId}
      jobId={jobId}
      source={source}
    />
  );
}
