# Video Clipper

Turn long videos into short, vertical clips.

## Architecture

This monorepo is organized into two applications:

- **`frontend/`** — Next.js (App Router) web UI for uploading videos, configuring clips, and viewing results.
- **`backend/`** — FastAPI API for uploads, validation, and media processing.

Use Node.js 22 (see `.nvmrc`) for frontend development and Python 3.13.5 for the backend.

## Run frontend and backend together

1. **Backend** (terminal 1):

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

2. **Frontend** (terminal 2):

```bash
cd frontend
cp .env.example .env.local   # first time only
yarn install
yarn dev
```

Open [http://localhost:3000](http://localhost:3000). Confirm the API with the [health check](#getting-started-backend) before importing a video.

The frontend reads `NEXT_PUBLIC_API_BASE_URL` from `frontend/.env.local` (see `frontend/.env.example`). Use the same host the browser can reach; the backend CORS default allows `http://localhost:3000`.

## Getting started (frontend only)

```bash
cd frontend
yarn install
yarn dev
```

## Scripts (frontend)

| Command       | Description              |
| ------------- | ------------------------ |
| `yarn dev`    | Development server       |
| `yarn build`  | Production build         |
| `yarn start`  | Serve production build   |
| `yarn lint`   | Run ESLint               |

## Getting started (backend)

Requires Python 3.13.5. **ffprobe** and **ffmpeg** must be on your `PATH` (or set `FFPROBE_PATH` / `FFMPEG_PATH`). The API **will not start** without both.

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) → `{"status":"ok"}`.

CORS allows `http://localhost:3000` by default (override with env vars supported by `pydantic-settings`).

### Video upload (Phase 2.1)

`POST /api/videos/upload` accepts a multipart `file` field, streams it to `DATA_DIR/jobs/<video_id>/`, validates it with **ffprobe**, and returns JSON metadata (`video_id`, duration, resolution, etc.). Files are not served publicly. Resolution is limited by `MAX_VIDEO_WIDTH` / `MAX_VIDEO_HEIGHT` (defaults allow up to 4K); later processing may normalize to a working file for clip generation.

**Upload cancellation:** the UI aborts the XHR, which closes the connection. The server checks `request.is_disconnected()` while reading, but Starlette may already have spooled part of the multipart body to disk before the handler runs—those bytes are not guaranteed to stop immediately. Partial job folders are removed when validation fails or the handler errors; aborted uploads may still leave spooled temp data outside the job directory until the request ends.

Copy `backend/.env.example` to `backend/.env` to tune limits. Keep `NEXT_PUBLIC_MAX_UPLOAD_BYTES` in `frontend/.env.local` aligned with `MAX_UPLOAD_BYTES`.

### YouTube import

`POST /api/videos/youtube` accepts `{ "url": "https://www.youtube.com/watch?v=…" }` (HTTPS only on the server), downloads via **yt-dlp** at **1080p or below** into the same `jobs/<video_id>/` layout, validates with **ffprobe**, and returns the same JSON shape as file upload. Only one import (upload or YouTube) runs at a time; concurrent requests receive a clear error.

**Import cancellation:** aborting the frontend request (or navigating away) stops the UI from waiting, but the server may continue downloading until its **timeout** (`YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS`) or completion. Partial job folders are removed when validation fails; a timed-out download may still briefly use CPU/network in the background until the worker thread finishes.

Requires **yt-dlp** on the machine running the backend (installed via `pip install -r requirements.txt`).

### Processing jobs (Phase 2.2 foundation)

`POST /api/jobs` accepts `{ "video_id": "<uuid>", "operation": "…" }` and returns **202** with a job record. Poll `GET /api/jobs/{job_id}` for `status` (`queued`, `processing`, `completed`, `failed`) and `progress` (0–1).

Operations:

- **`lifecycle_test`** — verifies the worker queue (no media output).
- **`generate_clips`** — splits the imported source into fixed-length **landscape** MP4 segments (default **60s**, configurable via `CLIP_TARGET_DURATION_SECONDS`) with FFmpeg (H.264 + AAC when audio exists). These files are 16:9-style working clips for trimming in the editor; they are **not** face-tracked 9:16 exports. Completed jobs return clip metadata; clips are listed at `GET /api/videos/{video_id}/clips` and streamed at `GET /api/videos/{video_id}/clips/{clip_id}` (supports **Range** requests).
- **`render_portrait_clip`** — enqueued by the portrait API (below): face-aware 9:16 render for one clip’s **saved** trim range.
- **`batch_export_clips`** — enqueued by the batch export API: renders portrait MP4s for selected clips (reusing cache when possible) and builds a ZIP.

Job metadata is stored under `DATA_DIR/processing_jobs/`. After a restart, jobs that were `queued` or `processing` are marked **failed** with an interrupted message. Only **one** active processing job per `video_id` is allowed at a time; concurrent requests receive **409** until the current job finishes.

`GET /api/videos/{video_id}/source` streams the imported `source.*` file for browser playback (supports **Range** requests). **Local assessment only** — there is no authentication; do not expose this API on the public internet.

### End-to-end workflow (Part 1)

1. **Import** — Upload a file or paste a YouTube URL. The backend stores `source.*` under `DATA_DIR/jobs/<video_id>/`.
2. **Generate clips** — The processing screen runs **`generate_clips`**. You get a list of landscape segments with suggested start/end times.
3. **Edit** — Open the editor, select a clip, and adjust trim boundaries (saved via `PATCH /api/videos/{video_id}/clips/{clip_id}`). Use **Original** to preview the full source; use **Clip** for the vertical preview.
4. **Portrait preview (9:16)** — With **Clip** selected, the frontend checks whether a portrait file exists for the current saved trim. If not, it calls **`POST …/portrait`**, polls **`GET /api/jobs/{job_id}`**, then plays **`GET …/portrait`** (same file used for export).
5. **Export** — Download one portrait MP4 (**`GET …/portrait/download`**) or batch-export selected clips as a ZIP (**`POST …/exports/batch`**, then **`GET …/exports/batch/{job_id}/download`**).

### Face tracking and portrait rendering (production)

Portrait output is produced by the live API, not by debug scripts. Implementation lives under `backend/app/services/tracking/` and `backend/app/services/portrait_render.py`.

For each portrait render the backend:

1. Reads the clip’s **saved** `[start_time, end_time]` from the clips manifest.
2. Runs **source analysis** once per video (cached under `DATA_DIR/jobs/<video_id>/analysis/`): YuNet face detection (bundled ONNX in `backend/models/`), scene cuts, primary-subject tracking, and a 9:16 crop path.
3. Slices the crop path for the clip range and encodes a **1080×1920** MP4 with FFmpeg (dynamic crop via `sendcmd`, H.264 + AAC when present).
4. Stores the result under `DATA_DIR/jobs/<video_id>/portraits/` and records it in `portraits.json`.

Re-rendering after a trim change reuses cached analysis when possible; only the clip range and encode are redone. `ANALYSIS_TIMEOUT_SECONDS` (default `1800`) caps a single analysis pass. Preview and export always use the **same** on-disk portrait file for a given saved trim.

### Portrait and batch export API

| Method | Path | Purpose |
| ------ | ---- | ------- |
| `POST` | `/api/videos/{video_id}/clips/{clip_id}/portrait` | Enqueue **`render_portrait_clip`** (**202**). Returns a job; poll `GET /api/jobs/{job_id}`. Serves cached output immediately when the render key already matches. |
| `GET` | `/api/videos/{video_id}/clips/{clip_id}/portrait` | Stream the current portrait MP4 for the saved trim (**Range** supported). **404** if none yet; **409** if a render is in progress. |
| `GET` | `/api/videos/{video_id}/clips/{clip_id}/portrait/download` | Download the same portrait file as an attachment. |
| `POST` | `/api/videos/{video_id}/exports/batch` | Enqueue **`batch_export_clips`** with selected clip IDs and trim revisions (**202**). |
| `GET` | `/api/videos/{video_id}/exports/batch/{job_id}/download` | Download the completed ZIP. |

### Optional development scripts

These CLI tools are **not** used by the web app. They call the same analysis/render services for local inspection and write gitignored output under `backend/data/debug/`:

```bash
cd backend
.venv/bin/python -m scripts.debug_tracking path/to/video.mp4 --start 20 --duration 30
.venv/bin/python -m scripts.render_portrait_clip path/to/video.mp4 --start 144 --end 174
```

- **`debug_tracking`** — Overlaid visualization of detections, crop box, and framing (development only).
- **`render_portrait_clip`** — One-off portrait MP4 using `render_portrait_clip()` (same function the API worker uses).

To exercise the real YuNet model on your own file in tests: `VIDEO_CLIPPER_FACE_TEST_VIDEO=path/to/video.mp4 pytest -m real_video`.

## Scripts (backend)

| Command | Description |
| ------- | ----------- |
| `pytest` | Run automated tests (from `backend/` with venv active) |
| `uvicorn app.main:app --reload` | Development API server on port 8000 |
| `python -m scripts.debug_tracking VIDEO` | Optional tracking visualization (development only) |
| `python -m scripts.render_portrait_clip VIDEO` | Optional one-off portrait render (development only) |
