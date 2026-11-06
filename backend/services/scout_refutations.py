"""Refutation finder: habitual opening moves of a scouted player that are bad.

Walks the scouted player's opening trees for positions where they are to move,
have been seen several times, and nearly always play the same move. Each such
move is checked with the engine (through an injected ``analyse`` callback, so
tests need no Stockfish); if it loses real evaluation, the position is reported
together with the best reply to punish it.
"""

from __future__ import annotations

import logging
from typing import Callable

import chess

from .opponent_scout import Node, _line_text, _mover_is_scouted

logger = logging.getLogger(__name__)

EVAL_CLIP = 10_000
MIN_LOSS_CP = 60
MISTAKE_CP = 100
BLUNDER_CP = 200
STILL_WINNING_CP = 300
MAX_RESULTS = 25
_SEVERITY_RANK = {"blunder": 0, "mistake": 1, "inaccuracy": 2}

Analyse = Callable[[chess.Board, int], list]


def _clip(value: float) -> int:
    return int(max(-EVAL_CLIP, min(EVAL_CLIP, value)))


def _severity(loss: int) -> str:
    if loss >= BLUNDER_CP:
        return "blunder"
    if loss >= MISTAKE_CP:
        return "mistake"
    return "inaccuracy"


def _candidates(trees: dict[str, Node], min_games: int, min_share: float):
    """Yield (color, node, path, modal_child) for habitual-move positions."""
    for color, root in trees.items():
        stack: list[tuple[Node, list[str]]] = [(root, [])]
        while stack:
            node, path = stack.pop()
            for child in node.children.values():
                stack.append((child, path + [child.san or ""]))
            if not _mover_is_scouted(node.ply + 1, color):
                continue
            if node.stats.n < min_games or not node.children:
                continue
            modal = max(node.children.values(), key=lambda c: (c.stats.n, c.san or ""))
            if modal.stats.n < 2 or modal.stats.n / node.stats.n < min_share:
                continue
            yield color, node, path, modal


def _top(result: list | None) -> dict | None:
    if not result:
        return None
    first = result[0]
    if not isinstance(first, dict) or first.get("eval") is None or not first.get("move"):
        return None
    return first


def _examine(color: str, node: Node, path: list[str], modal: Node, analyse: Analyse) -> dict | None:
    board = chess.Board(node.fen)
    try:
        move = board.parse_san(modal.san or "")
    except ValueError:
        return None

    before = _top(analyse(board, 1))
    if before is None:
        return None
    best_move = str(before["move"])
    if best_move == modal.san:
        return None
    eval_best = _clip(before["eval"])

    after_board = board.copy()
    after_board.push(move)
    fen_after = after_board.fen()
    if after_board.is_game_over():
        return None
    after = _top(analyse(after_board, 1))
    if after is None:
        return None
    eval_after = -_clip(after["eval"])
    loss = eval_best - eval_after
    if loss < MIN_LOSS_CP:
        return None
    if eval_after >= STILL_WINNING_CP and loss < STILL_WINNING_CP:
        return None

    punish_move = str(after["move"])
    pv = [str(m) for m in (after.get("pv") or [])]
    if not pv or pv[0] != punish_move:
        pv = [punish_move] + pv
    games = modal.stats.games
    score_pct = round(sum(g.score for g in games) / len(games) * 100, 1) if games else 0.0
    return {
        "opponent_color": color,
        "path": list(path),
        "line": _line_text(path),
        "fen": node.fen,
        "node_games": node.stats.n,
        "their_move": modal.san,
        "their_move_games": modal.stats.n,
        "their_share": round(modal.stats.n / node.stats.n * 100, 1),
        "their_score_pct": score_pct,
        "eval_best_cp": eval_best,
        "eval_after_cp": eval_after,
        "loss_cp": loss,
        "severity": _severity(loss),
        "best_move": best_move,
        "punish_move": punish_move,
        "punish_line": pv,
        "fen_after": fen_after,
    }


def find_refutations(
    trees: dict[str, Node],
    analyse: Analyse,
    *,
    min_games: int = 3,
    min_share: float = 0.5,
    max_positions: int = 60,
    progress: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """Habitual moves by the scouted player that the engine says are bad."""
    from stockfish_engine import EngineUnavailableError  # root-level module

    cands = list(_candidates(trees, min_games, min_share))
    cands.sort(key=lambda c: (-c[1].stats.n, c[0], c[2]))
    cands = cands[:max_positions]
    total = len(cands)

    found: list[dict] = []
    for done, (color, node, path, modal) in enumerate(cands, start=1):
        try:
            entry = _examine(color, node, path, modal, analyse)
        except EngineUnavailableError:
            raise
        except Exception:
            logger.warning("Refutation check failed at %s", " ".join(path), exc_info=True)
            entry = None
        if entry is not None:
            found.append(entry)
        if progress is not None:
            progress(done, total)

    found.sort(key=lambda e: (_SEVERITY_RANK[e["severity"]], -e["loss_cp"] * e["their_move_games"]))
    return found[:MAX_RESULTS]
