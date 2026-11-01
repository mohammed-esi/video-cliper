"use client";

import { useParams, useSearchParams } from "next/navigation";

import { AppHeader } from "@/components/layout/AppHeader";
import { Card } from "@/components/ui/Card";
import { FreshImportLink } from "@/features/import/FreshImportLink";
import { ErrorState } from "@/components/ui/ErrorState";
import { EditorScreen } from "@/features/editor/EditorScreen";
import { isUuid } from "@/lib/ids";

export function EditorRouteLoader() {
  const params = useParams<{ videoId: string }>();
  const searchParams = useSearchParams();
  const videoId = params.videoId;
  const clipParam = searchParams.get("clip");
  const initialClipId =
    clipParam && isUuid(clipParam) ? clipParam : null;

  if (!videoId || !isUuid(videoId)) {
    return (
      <>
        <AppHeader currentStep="edit" />
        <main id="main" className="flex flex-1 justify-center px-4 py-10 sm:px-6">
          <Card className="w-full max-w-lg p-6 shadow-pop sm:p-8">
            <ErrorState
              title="Invalid link"
              message="This editor link is not valid. Import a video to begin."
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
    <EditorScreen videoId={videoId} initialClipId={initialClipId} />
  );
}
