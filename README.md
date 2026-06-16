# Chess Review

A Chess.com-style game review app with a FastAPI backend, React frontend, and Stockfish analysis.

## Key Features

- Import recent Chess.com games by username.
- Paste or upload PGN text for analysis.
- Analyze games with Stockfish using fast, normal, or deep modes.
- Review move classifications, centipawn loss, best moves, and principal variations.
- Navigate the board with controls, move-list clicks, graph clicks, or left/right arrow keys.
- Show ECO/opening recognition when available.
- Flip the board and review only the imported user's moves.
- View player-insight summaries from recent Chess.com games.

## Project Structure

```text
backend/                 FastAPI API, serializers, Chess.com import, player insights
frontend/                React + Vite frontend
game_analyzer.py         PGN analysis orchestration
models.py                Analysis dataclasses and move classification
opening_recognition.py   ECO/opening recognition
pgn_parser.py            PGN parsing helpers
stockfish_engine.py      Stockfish wrapper
requirements.txt         Python dependencies
```

## Setup

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install frontend dependencies:

```bash
cd frontend
npm install
```

Install Stockfish and make sure it is available on your PATH, or configure a custom path in the app/backend payloads.

## Running Locally

Start the backend:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

Start the frontend:

```bash
cd frontend
npm run dev
```

Open the frontend URL printed by Vite. If another Vite app is already using port 5173, Vite may choose the next available port.

## Running With Docker

Build and run both services:

```bash
docker compose up --build
```

Open http://localhost:8080.

The Docker setup runs:

- `backend`: FastAPI on port 8001 inside the Docker network, with Stockfish installed from the Debian package.
- `frontend`: nginx serving the built React app on host port 8080.

The frontend calls `/api`, and nginx proxies those requests to the backend container. This keeps the browser-facing app on one origin and avoids hard-coded local API URLs.

Stop the stack:

```bash
docker compose down
```

## Deploying

The backend **requires Stockfish to be on the host** (`STOCKFISH_PATH`, defaults to `/usr/games/stockfish`). Both Dockerfiles install it via `apt-get install stockfish`, so deploy the backend using one of those Dockerfiles — a generic Python buildpack (no Dockerfile) won't have Stockfish available and `/analyze` will fail.

If the frontend and backend are hosted separately (e.g. frontend on Vercel, backend on Render/Fly/Railway):

- Set `VITE_API_BASE_URL` to the backend's full HTTPS URL as a **build-time** env var for the frontend (see `frontend/.env.example`). Leaving it unset falls back to `http://127.0.0.1:8001`, which only works for local dev.
- Serve the backend over HTTPS — an HTTPS frontend calling an HTTP backend gets blocked as mixed content.
- Add the frontend's deployed origin to `allow_origins`/`allow_origin_regex` in `backend/main.py` if it isn't already covered (Vercel preview URLs matching `https://chess-review*.vercel.app` are allowed via regex).

The root `Dockerfile` reads the listen port from `$PORT` (falls back to `8001` if unset), matching Render/Railway/Heroku-style platforms that inject `PORT`.

`/analyze`, `/chesscom/analyze`, and the Chess.com lookup endpoints are rate-limited per IP (in-memory, per process) to protect the Stockfish-backed endpoints from being overwhelmed on small instances.

In-memory caches (chess.com insights/repertoire, analysis results) are per-process with no persistence, so a restart or scale-to-zero clears them and the next request re-fetches/re-analyzes.
