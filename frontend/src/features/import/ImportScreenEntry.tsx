"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { Card } from "@/components/ui/Card";

import { resolveImportScreenMountKey } from "./import-navigation";
import { ImportScreen } from "./ImportScreen";

function ImportScreenKeyed() {
  const searchParams = useSearchParams();
  const mountKey = resolveImportScreenMountKey(searchParams);
  return <ImportScreen key={mountKey} />;
}

function ImportScreenEntryFallback() {
  return (
    <Card className="p-5 shadow-pop sm:p-6" aria-busy="true">
      <p className="sr-only">Loading import…</p>
    </Card>
  );
}

/** Home-route import UI: remounts when freshImport query param changes. */
export function ImportScreenEntry() {
  return (
    <Suspense fallback={<ImportScreenEntryFallback />}>
      <ImportScreenKeyed />
    </Suspense>
  );
}
