import type { ApiErrorBody } from "./types";

export class ApiRequestError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

export class UploadAbortError extends Error {
  constructor() {
    super("Upload cancelled.");
    this.name = "UploadAbortError";
  }
}

export function parseApiErrorBody(value: unknown): string | null {
  if (
    typeof value === "object" &&
    value !== null &&
    "message" in value &&
    typeof (value as ApiErrorBody).message === "string"
  ) {
    return (value as ApiErrorBody).message;
  }
  return null;
}

export function userFacingUploadError(error: unknown): string {
  if (error instanceof UploadAbortError) {
    return "";
  }
  if (error instanceof ApiRequestError) {
    return error.message;
  }
  return "We couldn't upload this video. Please try again.";
}

export function userFacingImportError(error: unknown): string {
  if (error instanceof UploadAbortError) {
    return "";
  }
  if (error instanceof ApiRequestError) {
    return error.message;
  }
  return "We couldn't import this video. Please try again.";
}

export function userFacingJobError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return error.message;
  }
  return "We couldn't start processing. Please try again.";
}
