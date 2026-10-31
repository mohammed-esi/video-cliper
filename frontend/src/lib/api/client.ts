import { getApiBaseUrl } from "./config";
import type { HealthResponse } from "./types";

function isHealthResponse(value: unknown): value is HealthResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    typeof (value as HealthResponse).status === "string"
  );
}

export async function fetchHealth(
  signal?: AbortSignal,
): Promise<HealthResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/health`, {
    signal,
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("Health check failed");
  }

  const data: unknown = await response.json();

  if (!isHealthResponse(data) || data.status !== "ok") {
    throw new Error("Unexpected health response");
  }

  return data;
}
