import { Suspense } from "react";

import { Card } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";

import { ProcessingRouteLoader } from "./ProcessingRouteLoader";

function ProcessingFallback() {
  return (
    <div className="flex flex-1 justify-center px-4 py-10 sm:px-6 md:py-14">
      <Card className="w-full max-w-lg p-6 shadow-pop sm:p-8">
        <ProgressBar label="Loading processing status…" value={undefined} />
      </Card>
    </div>
  );
}

export default function ProcessingPage() {
  return (
    <Suspense fallback={<ProcessingFallback />}>
      <ProcessingRouteLoader />
    </Suspense>
  );
}
