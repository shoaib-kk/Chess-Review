"""
Small Stockfish wrapper using python-chess.
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
from pathlib import Path

import chess
import chess.engine

logger = logging.getLogger(__name__)

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")

# Memory/CPU caps for constrained hosts (e.g. Render's small instances). Stockfish
# defaults are modest, but we set them explicitly so a single analysis can't grab
# more than we budgeted. Override via env vars without a code change.
STOCKFISH_HASH_MB = int(os.getenv("STOCKFISH_HASH_MB", "32"))
STOCKFISH_THREADS = int(os.getenv("STOCKFISH_THREADS", "1"))

# Serialises engine usage process-wide. The interactive /analyze path and the
# background puzzle miner each launch their own Stockfish; without this lock they
# can run concurrently and hold two NNUE nets in RAM at once, which OOM-kills small
# instances. The lock is held per game (acquired in __enter__, released in
# __exit__), so the two paths interleave at game boundaries rather than stacking.
_ENGINE_LOCK = threading.Lock()


def find_stockfish() -> str:
    project_dir = Path(__file__).resolve().parent
    local_stockfish_dir = project_dir / "stockfish"
    local_candidates = sorted(local_stockfish_dir.glob("stockfish*.exe"))

    candidates = [
        STOCKFISH_PATH,
        *local_candidates,
        shutil.which("stockfish"),
        shutil.which("stockfish.exe"),
        r"C:\Program Files\Stockfish\stockfish.exe",
        r"C:\Program Files (x86)\Stockfish\stockfish.exe",
    ]

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate

    raise RuntimeError(
        "Stockfish not found. Put the engine in the stockfish folder, install it on PATH, "
        "or enter the Stockfish executable path in the sidebar."
    )


class StockfishEngine:
    def __init__(self, path: str | None = None, depth: int = 16):
        self.path = path or find_stockfish()
        self.depth = depth
        self.engine: chess.engine.SimpleEngine | None = None

    def __enter__(self):
        # Acquire before launching so only one Stockfish process exists at a time.
        _ENGINE_LOCK.acquire()
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.path)
            try:
                self.engine.configure({"Hash": STOCKFISH_HASH_MB, "Threads": STOCKFISH_THREADS})
            except chess.engine.EngineError as exc:
                # Exotic builds may reject these option names; analysis still works.
                logger.warning("Could not set Hash/Threads on Stockfish: %s", exc)
        except Exception:
            _ENGINE_LOCK.release()
            raise
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.engine:
                self.engine.quit()
        finally:
            _ENGINE_LOCK.release()

    def configure(self, options: dict) -> None:
        """Set UCI options on the running engine (e.g. {"Skill Level": 8})."""
        if self.engine is None:
            raise RuntimeError("Stockfish engine is not running.")
        self.engine.configure(options)

    def analyse_position(
        self,
        board: chess.Board,
        *,
        depth: int | None = None,
        movetime_ms: int | None = None,
        include_pv: bool = True,
        pv_limit: int = 8,
    ):
        if self.engine is None:
            raise RuntimeError("Stockfish engine is not running.")

        limit = (
            chess.engine.Limit(time=movetime_ms / 1000)
            if movetime_ms is not None
            else chess.engine.Limit(depth=depth or self.depth)
        )
        info = self.engine.analyse(
            board,
            limit,
        )
        score = info["score"].pov(board.turn)
        eval_cp = score.score(mate_score=100000)

        if not include_pv:
            return eval_cp, None, []

        pv = info.get("pv", [])
        best_move = pv[0] if pv else None
        best_move_san = board.san(best_move) if best_move else None

        pv_san = []
        pv_board = board.copy()
        for move in pv[:pv_limit]:
            if move not in pv_board.legal_moves:
                break
            pv_san.append(pv_board.san(move))
            pv_board.push(move)

        return eval_cp, best_move_san, pv_san
