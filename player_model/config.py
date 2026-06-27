"""Central configuration, all overridable via environment variables."""

from __future__ import annotations

import os

# --- Database ---------------------------------------------------------------
# SQLite by default. Override with e.g. a Postgres URL if desired.
DATABASE_URL = os.getenv(
    "PM_DATABASE_URL",
    "sqlite:///./player_model.db",
)

# --- Celery / Redis ---------------------------------------------------------
REDIS_URL = os.getenv("PM_REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("PM_CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("PM_CELERY_RESULT_BACKEND", REDIS_URL)

# --- Stockfish --------------------------------------------------------------
STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")
# Analysis depth. Depth 18 is the spec default; make it configurable.
STOCKFISH_DEPTH = int(os.getenv("STOCKFISH_DEPTH", "18"))
STOCKFISH_HASH_MB = int(os.getenv("STOCKFISH_HASH_MB", "64"))
STOCKFISH_THREADS = int(os.getenv("STOCKFISH_THREADS", "1"))
# Number of candidate moves to request from the engine per position.
STOCKFISH_MULTIPV = int(os.getenv("STOCKFISH_MULTIPV", "3"))

# --- Classification thresholds (centipawn loss) -----------------------------
# Move is an inaccuracy/mistake/blunder when CPL exceeds these.
INACCURACY_CPL = int(os.getenv("PM_INACCURACY_CPL", "50"))
MISTAKE_CPL = int(os.getenv("PM_MISTAKE_CPL", "100"))
BLUNDER_CPL = int(os.getenv("PM_BLUNDER_CPL", "200"))

# --- Chess.com sync (Section 1) ---------------------------------------------
# Chess.com asks API clients to identify themselves in the User-Agent.
CHESSCOM_USER_AGENT = os.getenv(
    "PM_CHESSCOM_USER_AGENT",
    "PlayerModellingEngine/1.0 (contact: admin@example.com)",
)
# Incremental resync cadence for connected players (Celery beat), in hours.
SYNC_INTERVAL_HOURS = int(os.getenv("PM_SYNC_INTERVAL_HOURS", "6"))

# --- Ingestion --------------------------------------------------------------
# Flush positions to the DB in batches of this size.
BATCH_SIZE = int(os.getenv("PM_BATCH_SIZE", "50"))
# Cap a mate score to this many centipawns when storing as an integer.
MATE_SCORE_CP = int(os.getenv("PM_MATE_SCORE_CP", "100000"))
