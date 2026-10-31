"use client";

import { useEffect, useState } from "react";

import { fetchHealth } from "@/lib/api";

type StatusState = "loading" | "connected" | "unavailable";

export function BackendStatus() {
  const [status, setStatus] = useState<StatusState>("loading");

  useEffect(() => {
    const controller = new AbortController();

    fetchHealth(controller.signal)
      .then(() => {
        if (!controller.signal.aborted) {
          setStatus("connected");
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setStatus("unavailable");
        }
      });

    return () => {
      controller.abort();
    };
  }, []);

  const label =
    status === "loading"
      ? "Checking backend…"
      : status === "connected"
        ? "Backend connected"
        : "Backend unavailable";

  return (
    <p
      className="mt-8 inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-zinc-50 px-4 py-2 text-sm text-zinc-700"
      role="status"
      aria-live="polite"
      aria-busy={status === "loading"}
    >
      <span
        className={`size-2 shrink-0 rounded-full ${
          status === "loading"
            ? "animate-pulse bg-zinc-400"
            : status === "connected"
              ? "bg-emerald-500"
              : "bg-amber-500"
        }`}
        aria-hidden
      />
      {label}
    </p>
  );
}
