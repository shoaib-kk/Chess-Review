"""Run the Player Modelling Engine locally — no Docker, Redis or Celery worker.

This sets laptop-friendly defaults (a project-local SQLite DB and FAISS/PCA
artifact dirs, inline task execution, CORS for the Vite dev server) and starts
the API on http://127.0.0.1:8000. Background jobs (Chess.com sync, profile and
pattern computation, index build) run in an in-process worker thread, so the
twin becomes playable with just this one process running.

    python -m player_model.run_local            # default port 8000

Stockfish is located automatically from the bundled ``stockfish/`` directory,
``STOCKFISH_PATH`` or PATH. Set ``PM_INLINE_TASKS=0`` to use a real Redis broker
and a separate ``celery ... worker`` instead.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo root (one level up from this package).
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "player_model_data"


def _default(name: str, value: str) -> None:
    """Set an env var only if the user has not already provided one."""
    os.environ.setdefault(name, value)


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    # No broker/worker: run jobs inline in a background thread.
    _default("PM_INLINE_TASKS", "1")
    # Keep all state inside the repo so it's easy to find and wipe.
    _default("PM_DATABASE_URL", f"sqlite:///{(ROOT / 'player_model.db').as_posix()}")
    _default("PM_INDEX_DIR", str(DATA_DIR / "indices"))
    _default("PM_MODELS_DIR", str(DATA_DIR / "models"))
    # Must match the frontend's VITE_PM_API_KEY (defaults to "dev-master-key").
    _default("MASTER_API_KEY", "dev-master-key")
    # Allow the Vite dev server (both host spellings) through CORS.
    _default("FRONTEND_URL", "http://localhost:5173,http://127.0.0.1:5173")

    host = os.getenv("PM_HOST", "127.0.0.1")
    port = int(os.getenv("PM_PORT", "8000"))

    # Import uvicorn lazily so the env above is in place before the app loads.
    import uvicorn

    print(f"Player Modelling Engine -> http://{host}:{port}")
    print(f"  DB:       {os.environ['PM_DATABASE_URL']}")
    print(f"  Indices:  {os.environ['PM_INDEX_DIR']}")
    print(f"  Inline:   {os.environ['PM_INLINE_TASKS']} (no Redis/Celery worker needed)")
    uvicorn.run("player_model.api:app", host=host, port=port)


if __name__ == "__main__":
    main()
