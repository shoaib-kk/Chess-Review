from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("PUZZLE_DB_PATH", str(Path(__file__).resolve().parents[2] / "puzzles.db"))


def _connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def ensure_tables() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS puzzles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                game_url TEXT,
                game_date TEXT,
                move_number INTEGER,
                color TEXT,
                fen TEXT NOT NULL,
                played_move TEXT,
                best_move TEXT NOT NULL,
                best_move_uci TEXT,
                pv TEXT,
                cp_loss REAL,
                eval_before REAL,
                classification TEXT,
                solved INTEGER NOT NULL DEFAULT 0,
                UNIQUE(username, game_url, move_number)
            );
            CREATE TABLE IF NOT EXISTS analyzed_games (
                username TEXT NOT NULL,
                game_url TEXT NOT NULL,
                analyzed_at TEXT NOT NULL DEFAULT (datetime('now')),
                puzzle_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (username, game_url)
            );
        """)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(puzzles)")}
        if "eval_before" not in columns:
            conn.execute("ALTER TABLE puzzles ADD COLUMN eval_before REAL")
            # Puzzles are a derived cache. Old rows cannot be filtered reliably
            # because they predate the stored player-POV evaluation.
            conn.execute("DELETE FROM puzzles")
            conn.execute("DELETE FROM analyzed_games")


def get_analyzed_urls(username: str) -> set[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT game_url FROM analyzed_games WHERE username = ?", (username,)
        ).fetchall()
    return {row["game_url"] for row in rows}


def get_analyzed_count(username: str) -> int:
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM analyzed_games WHERE username = ?", (username,)
        ).fetchone()[0]


def mark_game_analyzed(username: str, game_url: str, puzzle_count: int = 0) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO analyzed_games (username, game_url, puzzle_count)"
            " VALUES (?, ?, ?)",
            (username, game_url, puzzle_count),
        )


def save_puzzle(
    *,
    username: str,
    game_url: str,
    game_date: str,
    move_number: int,
    color: str,
    fen: str,
    played_move: str,
    best_move: str,
    best_move_uci: str | None,
    pv: list[str],
    cp_loss: float,
    eval_before: float,
    classification: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO puzzles
               (username, game_url, game_date, move_number, color, fen,
                 played_move, best_move, best_move_uci, pv, cp_loss, eval_before, classification)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                username, game_url, game_date, move_number, color, fen,
                played_move, best_move, best_move_uci, json.dumps(pv), cp_loss, eval_before, classification,
            ),
        )


# Phase is derived from the full-move number on the board.
#   Opening    = move_number <= 12
#   Middlegame = 13..30
#   Endgame    = > 30
_PHASE_RANGES: dict[str, tuple[int | None, int | None]] = {
    "opening": (None, 12),
    "middlegame": (13, 30),
    "endgame": (31, None),
}

# Difficulty maps onto the stored `classification` column.
_DIFFICULTY_CLASSIFICATION: dict[str, str] = {
    "blunders": "Blunder",
    "mistakes": "Mistake",
}


def _phase_clause(phase: str | None) -> tuple[str, list]:
    """Return an SQL fragment + params restricting move_number to a phase range."""
    if not phase:
        return "", []
    bounds = _PHASE_RANGES.get(phase.strip().lower())
    if not bounds:
        return "", []
    low, high = bounds
    clause, params = "", []
    if low is not None:
        clause += " AND move_number >= ?"
        params.append(low)
    if high is not None:
        clause += " AND move_number <= ?"
        params.append(high)
    return clause, params


def _difficulty_clause(difficulty: str | None) -> tuple[str, list]:
    """Return an SQL fragment + params restricting classification to a difficulty."""
    if not difficulty:
        return "", []
    cls = _DIFFICULTY_CLASSIFICATION.get(difficulty.strip().lower())
    if not cls:
        return "", []
    return " AND classification = ?", [cls]


def get_puzzles(
    username: str,
    limit: int = 100,
    offset: int = 0,
    phase: str | None = None,
    difficulty: str | None = None,
) -> list[dict]:
    phase_sql, phase_params = _phase_clause(phase)
    diff_sql, diff_params = _difficulty_clause(difficulty)
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT * FROM puzzles
                WHERE username = ? AND eval_before >= 0{phase_sql}{diff_sql}
               ORDER BY cp_loss DESC LIMIT ? OFFSET ?""",
            (username, *phase_params, *diff_params, limit, offset),
        ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["pv"] = json.loads(d.get("pv") or "[]")
        d["solved"] = bool(d["solved"])
        result.append(d)
    return result


def get_puzzle_count(username: str) -> int:
    with _connect() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM puzzles WHERE username = ? AND eval_before >= 0", (username,)
        ).fetchone()[0]


def get_phase_counts(username: str) -> dict[str, int]:
    """Count available puzzles per phase (for the lobby), ignoring difficulty."""
    counts = {"all": 0, "opening": 0, "middlegame": 0, "endgame": 0}
    with _connect() as conn:
        rows = conn.execute(
            "SELECT move_number FROM puzzles WHERE username = ? AND eval_before >= 0", (username,)
        ).fetchall()
    for row in rows:
        move_number = row["move_number"] or 0
        counts["all"] += 1
        if move_number <= 12:
            counts["opening"] += 1
        elif move_number <= 30:
            counts["middlegame"] += 1
        else:
            counts["endgame"] += 1
    return counts


def mark_solved(username: str, puzzle_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE puzzles SET solved = 1 WHERE id = ? AND username = ?",
            (puzzle_id, username),
        )
