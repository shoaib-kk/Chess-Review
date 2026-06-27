"""Database engine, session factory, and startup helpers.

A single synchronous SQLAlchemy engine is shared process-wide. The app is
CPU-bound and synchronous (blocking Stockfish calls), so a sync engine matches
the existing architecture; there is no asyncio anywhere in the request path.
"""

from __future__ import annotations

import logging
import os
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

# `postgresql+psycopg://` selects the psycopg 3 driver. The default points at a
# locally reachable Postgres for bare `uvicorn` dev; Docker overrides it to the
# `db` service host. There is no SQLite fallback — Postgres is required.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://chess:chess@localhost:5432/chess",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models and Alembic's metadata."""


def get_session() -> Session:
    """FastAPI dependency yielding a session that is always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def wait_for_db(retries: int = 30, delay: float = 1.0) -> None:
    """Block until Postgres answers ``SELECT 1`` or retries are exhausted.

    Belt-and-suspenders alongside the Compose healthcheck: protects bare-metal
    dev and the brief window during which Postgres accepts connections before it
    is fully ready.
    """
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database reachable after %d attempt(s).", attempt)
            return
        except OperationalError as exc:  # pragma: no cover - timing dependent
            last_err = exc
            logger.warning("Database not ready (attempt %d/%d): %s", attempt, retries, exc)
            time.sleep(delay)
    raise RuntimeError(f"Database not reachable after {retries} attempts") from last_err
