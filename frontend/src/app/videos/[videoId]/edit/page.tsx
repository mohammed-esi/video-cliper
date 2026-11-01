import { Suspense } from "react";

import { Card } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";

import { EditorRouteLoader } from "./EditorRouteLoader";

function EditorFallback() {
  return (
    <div className="flex flex-1 justify-center px-4 py-10 sm:px-6">
      <Card className="w-full max-w-lg p-6 shadow-pop sm:p-8">
        <ProgressBar label="Loading editor…" value={undefined} />
      </Card>
    </div>
  );
}

export default function EditVideoPage() {
  return (
    <Suspense fallback={<EditorFallback />}>
      <EditorRouteLoader />
    </Suspense>
  );
}
