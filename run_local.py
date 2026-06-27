"""Local-dev launcher: run the backend against a SQLite file instead of Postgres.

The app normally requires Postgres (JSONB columns, Alembic-owned schema). For
quick local testing this shim:
  1. points DATABASE_URL at a local SQLite file,
  2. teaches SQLAlchemy to emit plain JSON for Postgres JSONB columns on SQLite,
  3. creates the tables directly (no Alembic),
then launches uvicorn exactly like `python -m uvicorn backend.main:app`.

Persistence is best-effort in the app, so the review/insights/puzzle flows all
work; data just lands in ./local_dev.db instead of Postgres.

    python run_local.py        # serves on http://127.0.0.1:8001
"""
from __future__ import annotations

import os

# 1. Use SQLite before anything imports backend.db (which reads DATABASE_URL).
os.environ.setdefault("DATABASE_URL", "sqlite:///./local_dev.db")
# Make sure the bundled Windows Stockfish is found even if STOCKFISH_PATH is set
# to a Linux default in the environment.
os.environ.pop("STOCKFISH_PATH", None)

# 2. Emit JSON instead of JSONB when the dialect is SQLite.
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def _compile_jsonb_as_json(element, compiler, **kw):  # noqa: ANN001
    return "JSON"


def main() -> None:
    import uvicorn

    from backend.db import Base, engine
    import backend.db_models  # noqa: F401  (registers tables on Base)

    Base.metadata.create_all(engine)

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8001, reload=False)


if __name__ == "__main__":
    main()
