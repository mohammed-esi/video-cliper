import { Suspense } from "react";

import { Card } from "@/components/ui/Card";
import { ProgressBar } from "@/components/ui/ProgressBar";

import { ExportRouteLoader } from "./ExportRouteLoader";

function ExportFallback() {
  return (
    <div className="flex flex-1 justify-center px-4 py-10 sm:px-6">
      <Card className="w-full max-w-lg p-6 shadow-pop sm:p-8">
        <ProgressBar label="Loading export…" value={undefined} />
      </Card>
    </div>
  );
}

export default function ExportVideoPage() {
  return (
    <Suspense fallback={<ExportFallback />}>
      <ExportRouteLoader />
    </Suspense>
  );
}
