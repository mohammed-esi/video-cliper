# Video Clipper

Turn long videos into short, vertical clips.

## Architecture

This monorepo is organized into two applications:

- **`frontend/`** — Next.js (App Router) web UI for uploading videos, configuring clips, and viewing results.
- **`backend/`** — FastAPI API for file handling and media processing (initialized; health check only for now).

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

Requires Python 3.13.5 and FFmpeg/ffprobe on your `PATH` (needed for later video features).

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) → `{"status":"ok"}`.

CORS allows `http://localhost:3000` by default (override with env vars supported by `pydantic-settings`).

## Scripts (backend)

| Command | Description |
| ------- | ----------- |
| `pytest` | Run automated tests (from `backend/` with venv active) |
| `uvicorn app.main:app --reload` | Development API server on port 8000 |
