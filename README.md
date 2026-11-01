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

Open [http://localhost:3000](http://localhost:3000). The homepage shows **Backend connected** when the API is reachable, or **Backend unavailable** if it is not.

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
- **`generate_clips`** — splits the imported source video into fixed-length MP4 clips (default **60s**, configurable via `CLIP_TARGET_DURATION_SECONDS`) with FFmpeg (H.264 + AAC when audio exists). Completed jobs return clip metadata; persisted clips are listed at `GET /api/videos/{video_id}/clips` and streamed at `GET /api/videos/{video_id}/clips/{clip_id}` (supports **Range** requests).

Job metadata is stored under `DATA_DIR/processing_jobs/`. After a restart, jobs that were `queued` or `processing` are marked **failed** with an interrupted message.

`GET /api/videos/{video_id}/source` streams the imported `source.*` file for browser playback (supports **Range** requests). **Local assessment only** — there is no authentication; do not expose this API on the public internet.

### Face tracking foundation (Phase 2.5.1, not wired into the API yet)

`backend/app/services/tracking/` analyzes a source video once (YuNet face detection from the bundled model in `backend/models/`, scene cuts, primary-subject tracking, 9:16 crop path) and caches the results as JSON under `DATA_DIR/jobs/<video_id>/analysis/`. Nothing in the running app calls it yet. `ANALYSIS_TIMEOUT_SECONDS` (default `1800`) limits one analysis pass.

To inspect the result on a real video, render a development-only debug video (gitignored, written to `backend/data/debug/`):

```bash
cd backend
.venv/bin/python -m scripts.debug_tracking path/to/video.mp4 --start 20 --duration 30
.venv/bin/python -m scripts.render_portrait_clip path/to/video.mp4 --start 144 --end 174
```

An opt-in test runs the real model on your own file: `VIDEO_CLIPPER_FACE_TEST_VIDEO=path/to/video.mp4 pytest -m real_video`.

## Scripts (backend)

| Command | Description |
| ------- | ----------- |
| `pytest` | Run automated tests (from `backend/` with venv active) |
| `uvicorn app.main:app --reload` | Development API server on port 8000 |
| `python -m scripts.debug_tracking VIDEO` | Render a tracking debug video (development only) |
