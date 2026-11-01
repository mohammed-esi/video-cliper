/** Mirrors backend `HealthResponse` (app/schemas). */
export interface HealthResponse {
  status: string;
}

/** Mirrors backend `VideoUploadResponse` (app/schemas/video.py). */
export interface VideoUploadResponse {
  video_id: string;
  original_filename: string;
  duration_seconds: number;
  width: number;
  height: number;
  has_audio: boolean;
  container: string;
}

export interface ApiErrorBody {
  message: string;
}

export interface YouTubeImportRequest {
  url: string;
}
