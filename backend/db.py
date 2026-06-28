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
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

# The local dev defaults, kept in one place so the credential guard below can
# recognise them precisely instead of pattern-matching on arbitrary substrings.
DEV_DB_USER = "chess"
DEV_DB_PASSWORD = "chess"
DEV_DATABASE_URL = f"postgresql+psycopg://{DEV_DB_USER}:{DEV_DB_PASSWORD}@localhost:5432/chess"


def _assert_strong_credentials(database_url: str, app_env: str) -> None:
    """Fail closed when a non-dev deploy ships with weak/default DB credentials.

    Forgetting to set ``DATABASE_URL`` is already handled; the gap this closes is
    a deploy that *does* set it but reuses the well-known local-dev secret
    ``chess:chess`` (or leaves the password empty). Those credentials are baked
    into compose/docs, so treating them as production-safe would be a silent
    foot-gun.

    We parse the URL and inspect the real username/password fields rather than
    doing a substring search, so a genuinely strong password that merely happens
    to contain the word "chess" (e.g. ``chess-7f3a...``) is never flagged.
    """
    if app_env == "dev":
        # Dev is allowed to use the weak local default by design.
        return
    try:
        url = make_url(database_url)
    except ArgumentError:
        # Let SQLAlchemy surface the real parse error later; we only guard creds.
        return

    username = url.username or ""
    password = url.password or ""

    # An empty/missing password is never acceptable outside dev — it implies
    # "trust" auth or a forgotten secret, both of which are insecure in prod.
    if not password:
        raise RuntimeError(
            "DATABASE_URL has no password. Set strong database credentials, "
            "or set APP_ENV=dev for local development."
        )

    # Exact match on the well-known dev secret — both the user *and* password
    # must be the literal "chess" for this to trip.
    if username == DEV_DB_USER and password == DEV_DB_PASSWORD:
        raise RuntimeError(
            "DATABASE_URL uses the weak local-dev credentials "
            f"({DEV_DB_USER!r}:{DEV_DB_PASSWORD!r}). Set strong, unique database "
            "credentials before deploying, or set APP_ENV=dev for local development."
        )


# `postgresql+psycopg://` selects the psycopg 3 driver. There is no SQLite
# fallback — Postgres is required. Fail closed: APP_ENV defaults to "production",
# so the weak `chess:chess` dev credentials are only ever used when APP_ENV=dev
# is set explicitly; a deploy that forgets to set DATABASE_URL raises at startup.
APP_ENV = os.getenv("APP_ENV", "production")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if APP_ENV == "dev":
        DATABASE_URL = DEV_DATABASE_URL
    else:
        raise RuntimeError("DATABASE_URL must be set unless APP_ENV is 'dev'.")

# Even when DATABASE_URL *is* set, refuse to boot a non-dev process with the
# default/weak credentials. This runs at import time but does not connect, so it
# is safe to exercise in tests without a live database.
_assert_strong_credentials(DATABASE_URL, APP_ENV)

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
