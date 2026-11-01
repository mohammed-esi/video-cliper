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

/** Mirrors backend `JobStatus` / `JobOperation` (app/schemas/job.py). */
export type JobStatus = "queued" | "processing" | "completed" | "failed";

export type JobOperation =
  | "lifecycle_test"
  | "generate_clips"
  | "render_portrait_clip"
  | "batch_export_clips";

/** Mirrors backend `JobResponse`. */
export interface JobResponse {
  job_id: string;
  video_id: string;
  operation: JobOperation;
  status: JobStatus;
  progress: number;
  created_at: string;
  updated_at: string;
  error_message: string | null;
  result: Record<string, unknown> | null;
}

/** Mirrors backend `ClipMetadata`. */
export interface ClipMetadata {
  clip_id: string;
  video_id: string;
  start_time: number;
  end_time: number;
  duration: number;
  generated_start_time: number;
  generated_end_time: number;
  storage_name: string;
  width: number;
  height: number;
  has_audio: boolean;
}

/** Mirrors backend `ClipListResponse`. */
export interface ClipListResponse {
  video_id: string;
  source_duration_seconds: number;
  clips: ClipMetadata[];
}
