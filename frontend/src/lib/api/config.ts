const DEFAULT_DEV_API_BASE_URL = "http://127.0.0.1:8000";

export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

  if (configured) {
    return configured.replace(/\/$/, "");
  }

  if (process.env.NODE_ENV === "development") {
    return DEFAULT_DEV_API_BASE_URL;
  }

  throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured");
}
