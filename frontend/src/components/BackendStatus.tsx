"use client";

import { useEffect, useState } from "react";

import { StatusPill, type StatusTone } from "@/components/ui/StatusPill";
import { fetchHealth } from "@/lib/api";

type StatusState = "loading" | "connected" | "unavailable";

const statusDisplay: Record<StatusState, { label: string; tone: StatusTone }> =
  {
    loading: { label: "Checking backend…", tone: "neutral" },
    connected: { label: "Backend connected", tone: "success" },
    unavailable: { label: "Backend unavailable", tone: "warning" },
  };

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

  const { label, tone } = statusDisplay[status];

  return (
    <StatusPill
      tone={tone}
      pulse={status === "loading"}
      role="status"
      aria-live="polite"
      aria-busy={status === "loading"}
    >
      {label}
    </StatusPill>
  );
}
