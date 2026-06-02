"""
Small Stockfish wrapper using python-chess.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import chess
import chess.engine


def find_stockfish() -> str:
    project_dir = Path(__file__).resolve().parent
    local_stockfish_dir = project_dir / "stockfish"
    local_candidates = sorted(local_stockfish_dir.glob("stockfish*.exe"))

    env_path = os.environ.get("STOCKFISH_PATH")
    candidates = [
        *local_candidates,
        env_path,
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
        self.engine = chess.engine.SimpleEngine.popen_uci(self.path)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.engine:
            self.engine.quit()

    def analyse_position(self, board: chess.Board):
        if self.engine is None:
            raise RuntimeError("Stockfish engine is not running.")

        info = self.engine.analyse(
            board,
            chess.engine.Limit(depth=self.depth),
        )
        score = info["score"].pov(board.turn)
        eval_cp = score.score(mate_score=100000)

        pv = info.get("pv", [])
        best_move = pv[0] if pv else None
        best_move_san = board.san(best_move) if best_move else None

        pv_san = []
        pv_board = board.copy()
        for move in pv[:8]:
            if move not in pv_board.legal_moves:
                break
            pv_san.append(pv_board.san(move))
            pv_board.push(move)

        return eval_cp, best_move_san, pv_san
