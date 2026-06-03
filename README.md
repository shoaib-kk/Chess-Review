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
