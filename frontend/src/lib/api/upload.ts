import {
  ApiRequestError,
  UploadAbortError,
  parseApiErrorBody,
} from "./errors";
import { getApiBaseUrl } from "./config";
import type { VideoUploadResponse } from "./types";

function isVideoUploadResponse(value: unknown): value is VideoUploadResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "video_id" in value &&
    typeof (value as VideoUploadResponse).video_id === "string" &&
    "duration_seconds" in value &&
    typeof (value as VideoUploadResponse).duration_seconds === "number"
  );
}

export interface UploadVideoOptions {
  onProgress?: (progress: number) => void;
  signal?: AbortSignal;
}

/**
 * Uploads a video with XMLHttpRequest so upload progress events are available.
 *
 * Aborting the request closes the connection; the server may still finish
 * spooling or validating bytes that were already received (see backend notes).
 */
export function uploadVideo(
  file: File,
  options: UploadVideoOptions = {},
): Promise<VideoUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${getApiBaseUrl()}/api/videos/upload`);
    xhr.responseType = "json";

    const handleAbort = () => {
      xhr.abort();
    };

    if (options.signal) {
      if (options.signal.aborted) {
        reject(new UploadAbortError());
        return;
      }
      options.signal.addEventListener("abort", handleAbort, { once: true });
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && options.onProgress) {
        options.onProgress(event.loaded / event.total);
      }
    };

    xhr.onload = () => {
      options.signal?.removeEventListener("abort", handleAbort);

      const body = xhr.response;
      if (xhr.status >= 200 && xhr.status < 300) {
        if (!isVideoUploadResponse(body)) {
          reject(new ApiRequestError("Unexpected response from the server."));
          return;
        }
        resolve(body);
        return;
      }

      const message =
        parseApiErrorBody(body) ??
        "We couldn't upload this video. Please try again.";
      reject(new ApiRequestError(message, xhr.status));
    };

    xhr.onerror = () => {
      options.signal?.removeEventListener("abort", handleAbort);
      reject(
        new ApiRequestError(
          "We couldn't reach the server. Check that the backend is running.",
        ),
      );
    };

    xhr.onabort = () => {
      options.signal?.removeEventListener("abort", handleAbort);
      reject(new UploadAbortError());
    };

    const formData = new FormData();
    formData.append("file", file, file.name);
    xhr.send(formData);
  });
}
