"use client";

import { useParams } from "next/navigation";

import { AppHeader } from "@/components/layout/AppHeader";
import { Card } from "@/components/ui/Card";
import { FreshImportLink } from "@/features/import/FreshImportLink";
import { ErrorState } from "@/components/ui/ErrorState";
import { ExportScreen } from "@/features/export/ExportScreen";
import { isUuid } from "@/lib/ids";

export function ExportRouteLoader() {
  const params = useParams<{ videoId: string }>();
  const videoId = params.videoId;

  if (!videoId || !isUuid(videoId)) {
    return (
      <>
        <AppHeader currentStep="export" />
        <main id="main" className="flex flex-1 justify-center px-4 py-10 sm:px-6">
          <Card className="w-full max-w-lg p-6 shadow-pop sm:p-8">
            <ErrorState
              title="Invalid link"
              message="This export link is not valid. Import a video to begin."
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

  return <ExportScreen videoId={videoId} />;
}
