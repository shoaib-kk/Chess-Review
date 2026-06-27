"""FAISS position index manager (Phase 5).

Builds and queries a per-player ``IndexFlatL2`` over encoded positions. Indices
live on disk (not in memory) and are loaded on demand through a small LRU cache
(max 20 players). Each player has three sidecar files under ``PM_INDEX_DIR``:

  {id}.faiss        — the FAISS flat index
  {id}_moves.json   — [{"fen", "move_played", "cpl", "game_id"}, ...] (row-aligned)
  {id}_meta.json    — {"version", "count", "profile_version"}
"""

from __future__ import annotations

import functools
import json
import os
import threading
from dataclasses import asdict, dataclass
from typing import Optional

import faiss
import numpy as np

from .encoding import VECTOR_DIM, encode_position

INDEX_DIR = os.getenv("PM_INDEX_DIR", "/data/indices")
_LRU_MAX_PLAYERS = 20
_WRITE_LOCK = threading.Lock()


@dataclass
class SimilarPosition:
    fen: str
    move_played: str
    cpl: int
    distance: float
    game_id: int

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Paths & metadata
# --------------------------------------------------------------------------- #
def _ensure_dir() -> None:
    os.makedirs(INDEX_DIR, exist_ok=True)


def _index_path(player_id: int) -> str:
    return os.path.join(INDEX_DIR, f"{player_id}.faiss")


def _moves_path(player_id: int) -> str:
    return os.path.join(INDEX_DIR, f"{player_id}_moves.json")


def _meta_path(player_id: int) -> str:
    return os.path.join(INDEX_DIR, f"{player_id}_meta.json")


def _read_meta(player_id: int) -> dict:
    try:
        with open(_meta_path(player_id), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"version": 0, "count": 0, "profile_version": None}


def _write_meta(player_id: int, count: int, profile_version: Optional[str]) -> int:
    prev = _read_meta(player_id).get("version", 0)
    version = prev + 1
    with open(_meta_path(player_id), "w", encoding="utf-8") as f:
        json.dump(
            {"version": version, "count": count, "profile_version": profile_version}, f
        )
    return version


def index_version(player_id: int) -> int:
    return _read_meta(player_id).get("version", 0)


# --------------------------------------------------------------------------- #
# On-demand loading with an LRU cache
# --------------------------------------------------------------------------- #
@functools.lru_cache(maxsize=_LRU_MAX_PLAYERS)
def _cached_load(player_id: int, version: int):
    index = faiss.read_index(_index_path(player_id))
    with open(_moves_path(player_id), encoding="utf-8") as f:
        moves = json.load(f)
    return index, moves


def _load(player_id: int):
    """Return (index, moves) for a player or (None, None) if not built yet."""
    if not os.path.exists(_index_path(player_id)):
        return None, None
    # Keying on the meta version makes the cache self-invalidate on rebuild/add.
    return _cached_load(player_id, index_version(player_id))


def clear_cache() -> None:
    _cached_load.cache_clear()


# --------------------------------------------------------------------------- #
# DB loading
# --------------------------------------------------------------------------- #
def _load_player_positions(player_id: int, db) -> list[dict]:
    from sqlalchemy import select

    from .models import Game, Position

    game_ids = list(db.scalars(select(Game.id).where(Game.player_id == player_id)))
    if not game_ids:
        return []
    rows = db.scalars(
        select(Position).where(Position.game_id.in_(game_ids)).order_by(
            Position.game_id, Position.ply
        )
    )
    return [
        {
            "fen": r.fen,
            "move_played": r.move_played,
            "cpl": int(r.cpl) if r.cpl is not None else 0,
            "game_id": r.game_id,
        }
        for r in rows
    ]


def _profile_version(player_id: int, db) -> Optional[str]:
    from .models import PlayerProfile

    profile = db.get(PlayerProfile, player_id)
    return profile.computed_at.isoformat() if profile and profile.computed_at else None


def _encode_batch(records: list[dict]) -> np.ndarray:
    if not records:
        return np.zeros((0, VECTOR_DIM), dtype=np.float32)
    return np.vstack([encode_position(r["fen"]) for r in records]).astype(np.float32)


# --------------------------------------------------------------------------- #
# Build / incremental add
# --------------------------------------------------------------------------- #
def build_position_index(player_id: int, db) -> faiss.Index:
    """(Re)build the FAISS index for a player from all stored positions."""
    _ensure_dir()
    records = _load_player_positions(player_id, db)
    vectors = _encode_batch(records)

    index = faiss.IndexFlatL2(VECTOR_DIM)
    if len(records):
        index.add(vectors)

    with _WRITE_LOCK:
        faiss.write_index(index, _index_path(player_id))
        with open(_moves_path(player_id), "w", encoding="utf-8") as f:
            json.dump(records, f)
        _write_meta(player_id, len(records), _profile_version(player_id, db))
    clear_cache()
    return index


def add_positions_to_index(player_id: int, new_positions: list) -> faiss.Index:
    """Incrementally add positions to an existing index (FAISS supports add()).

    ``new_positions`` items may be FEN strings or dicts with
    ``{fen, move_played, cpl, game_id}``; missing metadata is filled with blanks.
    """
    _ensure_dir()
    records = [
        {"fen": p, "move_played": "", "cpl": 0, "game_id": -1}
        if isinstance(p, str)
        else {
            "fen": p["fen"],
            "move_played": p.get("move_played", ""),
            "cpl": int(p.get("cpl", 0) or 0),
            "game_id": p.get("game_id", -1),
        }
        for p in new_positions
    ]

    if os.path.exists(_index_path(player_id)):
        index = faiss.read_index(_index_path(player_id))
        with open(_moves_path(player_id), encoding="utf-8") as f:
            moves = json.load(f)
    else:
        index = faiss.IndexFlatL2(VECTOR_DIM)
        moves = []

    if records:
        index.add(_encode_batch(records))
        moves.extend(records)

    with _WRITE_LOCK:
        faiss.write_index(index, _index_path(player_id))
        with open(_moves_path(player_id), "w", encoding="utf-8") as f:
            json.dump(moves, f)
        prev_profile = _read_meta(player_id).get("profile_version")
        _write_meta(player_id, len(moves), prev_profile)
    clear_cache()
    return index


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #
def find_similar_positions(
    fen: str, player_id: int, k: int = 10
) -> list[SimilarPosition]:
    """Return the k nearest stored positions to ``fen``, sorted by distance asc."""
    index, moves = _load(player_id)
    if index is None or index.ntotal == 0:
        return []

    query = encode_position(fen).reshape(1, -1)
    k = min(k, index.ntotal)
    distances, indices = index.search(query, k)

    results: list[SimilarPosition] = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0:
            continue
        m = moves[idx]
        results.append(
            SimilarPosition(
                fen=m["fen"],
                move_played=m["move_played"],
                cpl=m["cpl"],
                distance=float(dist),
                game_id=m["game_id"],
            )
        )
    # FAISS already returns ascending distance, but sort defensively.
    results.sort(key=lambda r: r.distance)
    return results
