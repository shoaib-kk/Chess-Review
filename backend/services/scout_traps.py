"""Find positions in an opponent's repertoire where a common reply is a trap.

A "trappy line" is a position where the scouted player is to move and the pool
of Lichess players at their level frequently answers with a move that scores
badly for the side playing it, while a better move exists. Logic is pure given
a ``fetch`` callable (fen -> Lichess explorer response).
"""

from __future__ import annotations

from typing import Any, Callable

from .lichess_explorer import LichessExplorerError
from .opponent_scout import Node, _iter_nodes, _line_text, _mover_is_scouted

LICHESS_BUCKETS = [0, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2500]
LICHESS_SPEEDS = ["ultraBullet", "bullet", "blitz", "rapid", "classical", "correspondence"]

# Approximate Lichess-minus-Chess.com rating offsets. Lichess ratings are
# usually higher; the gap varies by pool and level, so this is only a rough guide.
RATING_OFFSET = {"bullet": 250, "blitz": 250, "rapid": 200, "daily": 150}
DEFAULT_OFFSET = 225

MAX_CANDIDATE_PLY = 14
MIN_THEIR_GAMES = 2
MIN_TRAP_SHARE = 12.0     # % of the position's games
MIN_TRAP_GAMES = 50
MAX_TRAP_SCORE = 40.0     # % for the side playing the trap move
MIN_BEST_GAMES = 30
MIN_BEST_SCORE = 50.0
MAX_RESULTS = 12


def lichess_speeds(time_class: str | None) -> list[str]:
    tc = (time_class or "").lower()
    if tc == "bullet":
        return ["bullet"]
    if tc == "blitz":
        return ["blitz"]
    if tc == "rapid":
        return ["rapid"]
    if tc == "daily":
        return ["correspondence", "classical"]
    return ["blitz", "rapid"]


def lichess_rating_buckets(chesscom_rating: int | None, time_class: str | None) -> list[int]:
    """Two adjacent explorer rating buckets around the estimated Lichess rating (approximate)."""
    if not chesscom_rating:
        return [1400, 1600]
    est = chesscom_rating + RATING_OFFSET.get((time_class or "").lower(), DEFAULT_OFFSET)
    idx = 0
    for i, bucket in enumerate(LICHESS_BUCKETS):
        if est >= bucket:
            idx = i
    idx = min(idx, len(LICHESS_BUCKETS) - 2)
    return [LICHESS_BUCKETS[idx], LICHESS_BUCKETS[idx + 1]]


def rating_band_label(buckets: list[int]) -> str:
    """``[1400, 1600]`` -> ``"1400-1800"`` (a bucket spans up to the next bucket's start)."""
    if not buckets:
        return ""
    top = max(buckets)
    i = LICHESS_BUCKETS.index(top) if top in LICHESS_BUCKETS else -1
    upper = LICHESS_BUCKETS[i + 1] if 0 <= i < len(LICHESS_BUCKETS) - 1 else top
    return f"{min(buckets)}-{upper}"


def _games(entry: dict[str, Any]) -> int:
    return int(entry.get("white", 0) or 0) + int(entry.get("draws", 0) or 0) + int(entry.get("black", 0) or 0)


def _score_pct(entry: dict[str, Any], white_to_move: bool) -> float:
    total = _games(entry)
    if not total:
        return 0.0
    wins = entry.get("white", 0) if white_to_move else entry.get("black", 0)
    return (wins + 0.5 * entry.get("draws", 0)) / total * 100


def _detect_trap(response: dict[str, Any], white_to_move: bool) -> dict[str, Any] | None:
    total = _games(response)
    moves = [m for m in response.get("moves") or [] if m.get("san")]
    if not total or not moves:
        return None
    trap = None
    for m in moves:
        n = _games(m)
        share = n / total * 100
        score = _score_pct(m, white_to_move)
        if share >= MIN_TRAP_SHARE and n >= MIN_TRAP_GAMES and score <= MAX_TRAP_SCORE:
            if trap is None or share > trap["share"]:
                trap = {"san": m["san"], "share": share, "score": score, "games": n}
    if trap is None:
        return None
    best = None
    for m in moves:
        if m["san"] == trap["san"] or _games(m) < MIN_BEST_GAMES:
            continue
        score = _score_pct(m, white_to_move)
        if score >= MIN_BEST_SCORE and (best is None or score > best["score"]):
            best = {"san": m["san"], "score": score}
    if best is None:
        return None
    return {"total": total, "trap": trap, "best": best}


def _candidates(trees: dict[str, Node]) -> list[tuple[str, Node, list[str]]]:
    out = []
    for color, root in trees.items():
        for node, _parent, path in _iter_nodes(root):
            if node.ply > MAX_CANDIDATE_PLY or node.stats.n < MIN_THEIR_GAMES:
                continue
            if not _mover_is_scouted(node.ply + 1, color):
                continue
            out.append((color, node, path))
    out.sort(key=lambda c: (-c[1].stats.n, c[1].ply, c[2]))
    return out


def find_trappy_lines(
    trees: dict[str, Node],
    fetch: Callable[[str], dict],
    *,
    rating_band: str,
    speeds: list[str],
    max_positions: int = 20,
    progress: Callable[[int, int], None] | None = None,
) -> list[dict]:
    candidates = _candidates(trees)[:max_positions]
    results: list[tuple[tuple, dict]] = []
    total = len(candidates)

    for i, (color, node, path) in enumerate(candidates):
        try:
            response = fetch(node.fen)
        except LichessExplorerError:
            if i == 0:
                raise
            break
        if progress:
            progress(i + 1, total)
        found = _detect_trap(response, white_to_move=(color == "white"))
        if not found:
            continue
        trap, best = found["trap"], found["best"]
        theirs = sorted(node.children.values(), key=lambda c: (-c.stats.n, c.san or ""))
        played = next((c for c in theirs if c.san == trap["san"]), None)
        reason = (
            f"{trap['share']:.0f}% of players at this level play {trap['san']} here but score only "
            f"{trap['score']:.0f}% with it; {best['san']} scores {best['score']:.0f}%."
        )
        if played:
            reason += f" They have played {trap['san']} here in {played.stats.n} of their {node.stats.n} games."
        entry = {
            "opponent_color": color,
            "path": path,
            "line": _line_text(path),
            "fen": node.fen,
            "rating_band": rating_band,
            "speeds": list(speeds),
            "lichess_games": found["total"],
            "trap_move": trap["san"],
            "trap_share": round(trap["share"], 1),
            "trap_score_pct": round(trap["score"], 1),
            "best_move": best["san"],
            "best_score_pct": round(best["score"], 1),
            "their_games_here": node.stats.n,
            "their_moves_here": [{"san": c.san, "games": c.stats.n} for c in theirs],
            "reason": reason,
        }
        results.append(((played is not None, trap["share"] * found["total"]), entry))

    results.sort(key=lambda r: r[0], reverse=True)
    return [e for _k, e in results[:MAX_RESULTS]]
