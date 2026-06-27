# Chessspy

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
backend/db.py            SQLAlchemy engine, session factory, startup DB wait
backend/db_models.py     Game and Puzzle ORM models
backend/repositories/    Database helper functions (no SQL in route handlers)
frontend/                React + Vite frontend
alembic/                 Database migrations (Alembic)
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

## Database (PostgreSQL)

Reviewed games and generated puzzles are persisted in **PostgreSQL**. The schema
is two tables — `games` (each analysed game) and `puzzles` (one row per puzzle,
foreign-keyed to its game with `ON DELETE CASCADE`) — managed by **Alembic**
migrations (no `create_all()`).

Configuration is entirely environment-driven. Copy `.env.example` to `.env` and
adjust:

```bash
cp .env.example .env
```

| Variable | Purpose |
| --- | --- |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Credentials for the `db` container. |
| `DATABASE_URL` | SQLAlchemy connection string used by the backend **and** Alembic (`postgresql+psycopg://user:pass@host:5432/db`). |

When running the full stack with Docker (below), the database comes up
automatically — you do **not** need a local Postgres. For bare-metal backend dev
(`python -m uvicorn ...`) you must point `DATABASE_URL` at a reachable Postgres
(e.g. `docker compose up -d db`, or a local install).

Migrations are applied automatically on backend startup (the container entrypoint
runs `alembic upgrade head`). To create a new migration after changing the ORM
models:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

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

- `db`: PostgreSQL 17. Data is persisted in the named volume `pgdata`, so it
  survives `docker compose down` and rebuilds. **No port is published** — the
  database is reachable only on the internal Docker network, never from the
  public internet.
- `backend`: FastAPI on port 8001 inside the Docker network, with Stockfish
  installed from the Debian package. Waits for `db` to be healthy, applies
  Alembic migrations, then serves requests.
- `frontend`: nginx serving the built React app on host port 8080.

The frontend calls `/api`, and nginx proxies those requests to the backend container. This keeps the browser-facing app on one origin and avoids hard-coded local API URLs.

To wipe the database (e.g. for a clean start), remove the volume:

```bash
docker compose down -v
```

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

The root `Dockerfile` reads the listen port from `$PORT` (falls back to `8001` if unset), matching Render/Railway/Heroku-style platforms that inject `PORT`. It also runs `alembic upgrade head` on boot, so set **`DATABASE_URL`** to a reachable PostgreSQL instance (a managed/private database — never expose it publicly). On the DigitalOcean droplet, `docker compose up --build` provisions the internal `db` service for you and no Postgres port is published to the host.

`/analyze`, `/chesscom/analyze`, and the Chess.com lookup endpoints are rate-limited per IP (in-memory, per process) to protect the Stockfish-backed endpoints from being overwhelmed on small instances. Puzzle generation (`POST /puzzles/{username}/analyze`), which launches background Stockfish analysis over up to ~200 games, has its own stricter per-IP limit.

In-memory caches (chess.com insights/repertoire, analysis results) are per-process with no persistence, so a restart or scale-to-zero clears them and the next request re-fetches/re-analyzes.
