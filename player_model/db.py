"""SQLAlchemy engine, session factory and Base."""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

# SQLite needs check_same_thread off so the Celery worker and the API process
# can each open connections. For non-SQLite URLs these args are ignored.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    future=True,
    pool_pre_ping=True,
)


if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _record):  # pragma: no cover - infra
        cursor = dbapi_connection.cursor()
        # WAL lets the worker write while the API reads concurrently;
        # foreign_keys must be enabled per-connection for ON DELETE CASCADE.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables. Idempotent; safe to call on every boot."""
    from . import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    _ensure_sync_columns()


# Additive, idempotent upgrade for databases created before the Chess.com sync
# columns existed. ``create_all`` never ALTERs an existing table, so we add the
# nullable columns and the per-player URL dedup index by hand. All statements use
# IF NOT EXISTS / a guarded ALTER so re-running is harmless.
_SYNC_COLUMNS = {
    "players": [
        ("chess_com_username", "VARCHAR(128)"),
        ("avatar_url", "VARCHAR(512)"),
        ("last_synced_at", "DATETIME"),
        ("last_game_end_time", "INTEGER"),
    ],
    "games": [
        ("source", "VARCHAR(16) DEFAULT 'pgn' NOT NULL"),
        ("chess_com_game_url", "VARCHAR(256)"),
        ("time_class", "VARCHAR(16)"),
        ("end_time", "INTEGER"),
    ],
}


def _ensure_sync_columns() -> None:  # pragma: no cover - exercised via init_db
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _SYNC_COLUMNS.items():
            if table not in existing_tables:
                continue  # create_all already built it with every column
            present = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_games_player_url "
                "ON games (player_id, chess_com_game_url)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_players_chess_com_username "
                "ON players (chess_com_username)"
            )
        )
