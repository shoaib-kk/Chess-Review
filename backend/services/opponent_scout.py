"""Opponent scouting: what does a player know, and where are they weak?

Everything here is computed from the opponent's public Chess.com games. The
module is split into a pure part (``parse_game`` / ``build_scouting_report``,
unit-tested in ``tests/test_opponent_scout.py``) and two impure edges: fetching
games (``get_scouting_report``) and the optional Stockfish pass that scores the
position each game reached at move 12 (``_engine_evals``).

Key ideas, all from the opponent's point of view:

* **Rating-adjusted performance.** Raw win rate is confounded by who they were
  paired against, so every group carries the Elo-expected score and the
  difference (``perf_delta``). A shrunk version (``shrunk_delta``) pulls small
  samples toward zero so a 2-game fluke never tops the weakness list.
* **Familiarity.** How well they *know* an opening: how often they play it, how
  deep their established move order goes before they deviate from it
  (``book_depth``), and how fast they play its first ten moves compared with
  their own norm (clock data from the PGN ``[%clk]`` comments).
* **Opening tree.** A move tree (both sides' moves) with stats per node, so the
  UI can walk lines and the report can surface concrete positions to steer into
  or avoid.
"""

from __future__ import annotations

import io
import logging
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Any, Iterable

import chess
import chess.pgn

from opening_recognition import recognise_opening

from .cache import ttl_lru_cache
from .chesscom_client import get_recent_games
from .opening_names import OPENING_FAMILY_PREFIXES, extract_opening_family, extract_variation

logger = logging.getLogger(__name__)

DRAW_CODES = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}
LOSS_REASONS = {
    "checkmated": "checkmate",
    "resigned": "resignation",
    "timeout": "time",
    "abandoned": "abandoned",
}

TREE_MAX_PLIES = 16          # explorer depth (8 full moves)
TREE_MIN_GAMES_DEEP = 2      # below ply 4, only keep nodes seen at least twice
EVAL_PLY = 24                # "out of the opening" = position after Black's 12th move
EVAL_CLIP_CP = 800           # clip evals so one mate score can't swamp an average
OPENING_CLOCK_MOVES = 10     # own moves counted for opening clock usage
SHRINK_K = 5                 # pseudo-games of "performs as expected" prior
EARLY_LOSS_MOVES = 25        # a loss in <= this many full moves is an opening-ish collapse
BOOK_MIN_GAMES = 3           # a node needs this many games to count as "established"

FAMILY_TERMINALS = {"opening", "defense", "defence", "game", "attack", "gambit", "countergambit", "system"}
VARIATION_TERMINALS = {"variation", "attack", "defense", "defence", "line", "system", "gambit", "countergambit"}
# Chess.com slugs drop apostrophes ("Kings-Indian-Defense"); restore the common ones
# so names match the known families in ``opening_names``.
POSSESSIVES = {
    "Kings": "King's", "Queens": "Queen's", "Bishops": "Bishop's", "Petrovs": "Petrov's", "Owens": "Owen's",
    "Alekhines": "Alekhine", "Birds": "Bird",
}


# ── small helpers ─────────────────────────────────────────────────────────────


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def _avg(values: Iterable[float | None], digits: int = 1) -> float | None:
    clean = [v for v in values if v is not None]
    return round(mean(clean), digits) if clean else None


def expected_score(own: int | None, other: int | None) -> float | None:
    """Elo expected score for a player rated ``own`` against ``other``."""
    if own is None or other is None:
        return None
    return 1.0 / (1.0 + 10 ** ((other - own) / 400.0))


def shrunk_delta(score_sum: float, expected_sum: float, n: int, k: int = SHRINK_K) -> float:
    """Average (score - expected) per game, shrunk toward 0 by ``k`` pseudo-games."""
    if n <= 0:
        return 0.0
    return (score_sum - expected_sum) / (n + k)


def confidence_label(n: int) -> str:
    if n >= 12:
        return "high"
    if n >= 5:
        return "medium"
    return "low"


def parse_time_control(raw: str | None) -> tuple[float | None, float]:
    """``"180+2"`` -> (180, 2). Daily (``"1/259200"``) and unknown -> (None, 0)."""
    if not raw or "/" in raw:
        return None, 0.0
    base, _, inc = raw.partition("+")
    try:
        return float(base), float(inc or 0)
    except ValueError:
        return None, 0.0


def _strip_move_tokens(words: list[str]) -> list[str]:
    out = []
    for word in words:
        if re.match(r"^\d+\.", word) or re.match(r"^\d+$", word) or re.match(r"^[a-hKQRBNO][a-h1-8x+#=O-]{1,6}$", word) and any(c.isdigit() for c in word):
            break
        out.append(word)
    return out


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.casefold().replace("'", ""))


def opening_from_eco_url(url: str | None) -> str | None:
    """Turn Chess.com's ECOUrl slug into a readable opening name (no move suffix).

    ``.../openings/Sicilian-Defense-Najdorf-Variation-6.Be3-e5`` ->
    ``Sicilian Defense Najdorf Variation``.
    """
    if not url or "/openings/" not in url:
        return None
    slug = url.rstrip("/").split("/openings/")[-1]
    # Move suffixes come as "-6.Be3-e5" or glued on as "Defense...6.cxd4".
    slug = re.split(r"\.\.\.|-\d+\.", slug)[0]
    words = _strip_move_tokens([w for w in slug.split("-") if w])
    name = " ".join(words).strip()
    if not name or name.casefold() == "undefined":
        return None
    return name


def split_opening(name: str) -> tuple[str, str | None]:
    """Split an opening name into (family, short variation).

    Known families (``opening_names``) win; otherwise the family runs up to the
    first word like Opening/Defense/Game/Attack. The variation is cut at its own
    first terminal word, so "Najdorf Variation English Attack" groups as
    "Najdorf Variation".
    """
    words = [POSSESSIVES.get(w, w) for w in name.replace(",", " ").replace(":", " ").split()]
    name = " ".join(words)
    family = extract_opening_family(name)
    consumed = None
    if family != name:
        # Known family: find how many name words it spans ("Caro Kann Defense"
        # matches "Caro-Kann Defense"), comparing punctuation-insensitively.
        target = _compact(family)
        for i in range(1, len(words) + 1):
            if _compact(" ".join(words[:i])) == target:
                consumed = i
                break
    if consumed is None and family == name:
        # Known family named mid-way: "Alapin Sicilian Defense", "Magnus Sicilian".
        compact_words = [_compact(w) for w in words]
        for known in OPENING_FAMILY_PREFIXES:
            known_words = [_compact(w) for w in known.replace("-", " ").split()]
            head = known_words if len(known_words) == 1 else known_words[:1]
            for i in range(1, len(words)):
                if compact_words[i : i + len(head)] == head:
                    span = len(known_words) if compact_words[i : i + len(known_words)] == known_words else len(head)
                    leftover = words[:i] + words[i + span:]
                    if leftover and leftover[-1].lower() in {"variation", "defense", "defence"}:
                        leftover = leftover[:-1]
                    return known, " ".join(leftover + ["Variation"]) if leftover else None
    if consumed is None:
        # Unknown family (or an alias spelled differently): cut at the first
        # family terminal word, keeping an alias-normalised family if we have one.
        for i, word in enumerate(words):
            if word.lower() in FAMILY_TERMINALS:
                if family == name:
                    family = " ".join(words[: i + 1])
                consumed = i + 1
                break
        else:
            return name, None
    rest = words[consumed:]
    if rest and rest[0].lower() in {"opening", "game"}:
        rest = rest[1:]
    if not rest:
        return family, None
    for i, word in enumerate(rest):
        if word.lower() in VARIATION_TERMINALS:
            return family, " ".join(rest[: i + 1])
    return family, " ".join(rest[:4])


# ── per-game parsing ──────────────────────────────────────────────────────────


@dataclass
class ScoutGame:
    """One game reduced to what scouting needs, from the scouted player's POV."""

    color: str                      # "white" | "black" (the scouted player's side)
    score: float                    # 1 / 0.5 / 0
    expected: float | None
    own_rating: int | None
    foe_rating: int | None
    foe: str
    sans: list[str]                 # first TREE_MAX_PLIES plies
    fens: list[str]                 # fen after each ply in ``sans``
    ply_count: int
    family: str
    variation: str | None
    eco: str
    time_class: str | None
    end_time: int
    date: str | None
    url: str | None
    accuracy: float | None
    result_reason: str              # how it ended, from their POV: "win:resignation", "loss:time", "draw:agreed"...
    move_time_pct: list[float | None] = field(default_factory=list)  # per ply; % of base clock spent (own moves only)
    opening_time_pct: float | None = None   # % of base clock used on first OPENING_CLOCK_MOVES own moves
    first_long_think: int | None = None     # full-move number of first long think (<= move 15)
    fen_at_eval: str | None = None
    eval_cp: float | None = None            # engine eval at EVAL_PLY, scouted player's POV
    book_depth: float = 0.0                 # filled after the tree is built

    @property
    def result(self) -> str:
        return "win" if self.score == 1 else "draw" if self.score == 0.5 else "loss"

    @property
    def full_moves(self) -> int:
        return (self.ply_count + 1) // 2

    @property
    def is_early_loss(self) -> bool:
        return self.score == 0 and self.full_moves <= EARLY_LOSS_MOVES


def _int(raw: str | None) -> int | None:
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def _result_reason(own_code: str | None, foe_code: str | None) -> tuple[float, str]:
    if own_code == "win":
        return 1.0, f"win:{LOSS_REASONS.get(foe_code or '', 'other')}"
    if own_code in DRAW_CODES:
        return 0.5, f"draw:{own_code}"
    return 0.0, f"loss:{LOSS_REASONS.get(own_code or '', 'other')}"


def _clock_profile(game: chess.pgn.Game, white: bool, base: float | None, inc: float) -> tuple[list[float | None], float | None, int | None]:
    """Per-ply % of base clock spent (own moves), opening clock usage, first long think."""
    per_ply: list[float | None] = []
    spent_seconds: list[float] = []
    if not base:
        return per_ply, None, None
    prev = base
    for ply, node in enumerate(game.mainline()):
        own = (ply % 2 == 0) == white
        if not own:
            per_ply.append(None)
            continue
        clock = node.clock()
        if clock is None:
            per_ply.append(None)
            continue
        spent = max(0.0, prev - clock + inc)
        prev = clock
        spent_seconds.append(spent)
        per_ply.append(round(spent / base * 100, 2))
        if len(per_ply) > 60:
            break

    opening_pct = None
    if len(spent_seconds) >= 6:
        opening_pct = round(sum(spent_seconds[:OPENING_CLOCK_MOVES]) / base * 100, 1)

    first_think = None
    window = spent_seconds[:15]
    if len(window) >= 6:
        threshold = max(0.04 * base, 3 * median(window), 2.0)
        for i, spent in enumerate(window):
            if i > 0 and spent >= threshold:  # skip move 1 (premove / connection noise)
                first_think = i + 1
                break
    return per_ply, opening_pct, first_think


def parse_game(raw: dict[str, Any], username: str) -> ScoutGame | None:
    """Reduce a cleaned Chess.com game dict to a ``ScoutGame`` (or None if not theirs)."""
    target = username.casefold()
    if (raw.get("white_username") or "").casefold() == target:
        white = True
    elif (raw.get("black_username") or "").casefold() == target:
        white = False
    else:
        return None
    if raw.get("rules") not in (None, "chess"):
        return None

    try:
        game = chess.pgn.read_game(io.StringIO(raw.get("pgn") or ""))
    except Exception:
        return None
    if game is None:
        return None

    board = game.board()
    if board.fen() != chess.STARTING_FEN:
        return None  # custom start positions / chess960 slip-throughs

    sans: list[str] = []
    fens: list[str] = []
    fen_at_eval = None
    ply_count = 0
    for move in game.mainline_moves():
        try:
            san = board.san(move)
            board.push(move)
        except Exception:
            break
        ply_count += 1
        if ply_count <= TREE_MAX_PLIES:
            sans.append(san)
            fens.append(board.fen())
        if ply_count == EVAL_PLY and not board.is_game_over():
            fen_at_eval = board.fen()

    headers = game.headers
    own_rating = _int(headers.get("WhiteElo" if white else "BlackElo"))
    foe_rating = _int(headers.get("BlackElo" if white else "WhiteElo"))
    own_code = raw.get("white_result" if white else "black_result")
    foe_code = raw.get("black_result" if white else "white_result")
    score, reason = _result_reason(own_code, foe_code)

    name = opening_from_eco_url(headers.get("ECOUrl"))
    if not name:
        recognised = recognise_opening(game)
        name = recognised.name if recognised else headers.get("Opening") or "Unknown"
        family, variation = extract_opening_family(name), extract_variation(name)
    else:
        family, variation = split_opening(name)

    base, inc = parse_time_control(raw.get("time_control") or headers.get("TimeControl"))
    per_ply, opening_pct, first_think = _clock_profile(game, white, base, inc)

    accuracy = raw.get("white_accuracy" if white else "black_accuracy")
    try:
        accuracy = round(float(accuracy), 1) if accuracy is not None else None
    except (TypeError, ValueError):
        accuracy = None

    return ScoutGame(
        color="white" if white else "black",
        score=score,
        expected=expected_score(own_rating, foe_rating),
        own_rating=own_rating,
        foe_rating=foe_rating,
        foe=raw.get("black_username" if white else "white_username") or "",
        sans=sans,
        fens=fens,
        ply_count=ply_count,
        family=family or "Unknown",
        variation=variation,
        eco=headers.get("ECO", "?"),
        time_class=raw.get("time_class"),
        end_time=raw.get("end_time") or 0,
        date=raw.get("date"),
        url=raw.get("url"),
        accuracy=accuracy,
        result_reason=reason,
        move_time_pct=per_ply[:TREE_MAX_PLIES],
        opening_time_pct=opening_pct,
        first_long_think=first_think,
        fen_at_eval=fen_at_eval,
    )


# ── aggregation ───────────────────────────────────────────────────────────────


class Stats:
    """Accumulates result / expectation / clock / engine numbers for a group of games."""

    def __init__(self) -> None:
        self.games: list[ScoutGame] = []

    def add(self, game: ScoutGame) -> None:
        self.games.append(game)

    @property
    def n(self) -> int:
        return len(self.games)

    def delta_parts(self) -> tuple[float, float, int]:
        rated = [g for g in self.games if g.expected is not None]
        return sum(g.score for g in rated), sum(g.expected for g in rated), len(rated)  # type: ignore[misc]

    @property
    def shrunk(self) -> float:
        s, e, n = self.delta_parts()
        return shrunk_delta(s, e, n)

    def to_dict(self, total: int | None = None) -> dict[str, Any]:
        games = self.games
        n = len(games)
        wins = sum(1 for g in games if g.score == 1)
        draws = sum(1 for g in games if g.score == 0.5)
        s, e, rated_n = self.delta_parts()
        evals = [max(-EVAL_CLIP_CP, min(EVAL_CLIP_CP, g.eval_cp)) for g in games if g.eval_cp is not None]
        return {
            "games": n,
            "frequency": _pct(n, total) if total else None,
            "wins": wins,
            "draws": draws,
            "losses": n - wins - draws,
            "score_pct": _pct(sum(g.score for g in games), n),
            "expected_pct": _pct(e, rated_n) if rated_n else None,
            "perf_delta": round((s - e) / rated_n * 100, 1) if rated_n else None,
            "shrunk_delta": round(shrunk_delta(s, e, rated_n) * 100, 1),
            "confidence": confidence_label(n),
            "avg_accuracy": _avg(g.accuracy for g in games),
            "avg_eval_cp": round(mean(evals)) if evals else None,
            "evaluated_games": len(evals),
            "early_loss_rate": _pct(sum(1 for g in games if g.is_early_loss), n),
            "avg_opening_time_pct": _avg(g.opening_time_pct for g in games),
            "avg_book_depth": _avg((g.book_depth for g in games), 1) if n else None,
            "avg_first_think": _avg(g.first_long_think for g in games),
            "avg_opp_rating": round(mean([g.foe_rating for g in games if g.foe_rating])) if any(g.foe_rating for g in games) else None,
            "last_played": max((g.date for g in games if g.date), default=None),
        }


@dataclass
class Node:
    san: str | None
    ply: int
    fen: str
    stats: Stats = field(default_factory=Stats)
    children: dict[str, "Node"] = field(default_factory=dict)
    time_pcts: list[float] = field(default_factory=list)  # clock spent on *this* move, if theirs

    def child(self, san: str, fen: str) -> "Node":
        node = self.children.get(san)
        if node is None:
            node = Node(san=san, ply=self.ply + 1, fen=fen)
            self.children[san] = node
        return node


def build_tree(games: list[ScoutGame], color: str) -> Node:
    root = Node(san=None, ply=0, fen=chess.STARTING_FEN)
    for game in games:
        if game.color != color:
            continue
        node = root
        node.stats.add(game)
        for i, san in enumerate(game.sans):
            node = node.child(san, game.fens[i])
            node.stats.add(game)
            spent = game.move_time_pct[i] if i < len(game.move_time_pct) else None
            if spent is not None:
                node.time_pcts.append(spent)
    return root


def _mover_is_scouted(ply_after: int, color: str) -> bool:
    """Was the move that *led to* a node at ``ply_after`` played by the scouted player?"""
    white_moved = ply_after % 2 == 1
    return white_moved == (color == "white")


def assign_book_depth(games: list[ScoutGame], trees: dict[str, Node]) -> None:
    """How many of their own moves follow their established (modal) choice.

    Walk each game through its colour's tree. At every node where the scouted
    player is to move and the node is established (>= BOOK_MIN_GAMES games), the
    move counts as "book" if it's their most common choice there. Stop at the
    first deviation or the first unestablished node.
    """
    for game in games:
        node = trees[game.color]
        depth = 0
        for san in game.sans:
            to_move_is_scouted = _mover_is_scouted(node.ply + 1, game.color)
            nxt = node.children.get(san)
            if nxt is None:
                break
            if to_move_is_scouted:
                if node.stats.n < BOOK_MIN_GAMES:
                    break
                modal = max(node.children.values(), key=lambda c: c.stats.n)
                if modal.san != san or modal.stats.n < 2:
                    break
                depth += 1
            node = nxt
        game.book_depth = float(depth)


def _line_text(sans: list[str], start_ply: int = 0) -> str:
    parts = []
    for i, san in enumerate(sans):
        ply = start_ply + i
        if ply % 2 == 0:
            parts.append(f"{ply // 2 + 1}. {san}")
        elif i == 0:
            parts.append(f"{ply // 2 + 1}... {san}")
        else:
            parts.append(san)
    return " ".join(parts)


def serialize_tree(node: Node, color: str, path: list[str] | None = None) -> dict[str, Any]:
    path = path or []
    children = sorted(node.children.values(), key=lambda c: (-c.stats.n, c.san or ""))
    kept = [c for c in children if c.ply <= 4 or c.stats.n >= TREE_MIN_GAMES_DEEP]
    total = node.stats.n
    data = {
        "san": node.san,
        "ply": node.ply,
        "path": path,
        "fen": node.fen,
        "by": None if node.san is None else ("them" if _mover_is_scouted(node.ply, color) else "you"),
        "avg_time_pct": _avg(node.time_pcts, 2),
        **{k: v for k, v in node.stats.to_dict(total=None).items() if k in {
            "games", "wins", "draws", "losses", "score_pct", "expected_pct", "perf_delta",
            "shrunk_delta", "avg_eval_cp", "evaluated_games", "avg_accuracy",
        }},
        "children": [],
    }
    for child in kept:
        child_dict = serialize_tree(child, color, path + [child.san or ""])
        child_dict["frequency"] = _pct(child.stats.n, total)
        data["children"].append(child_dict)
    return data


def _iter_nodes(node: Node, path: list[str] | None = None):
    path = path or []
    for child in node.children.values():
        child_path = path + [child.san or ""]
        yield child, node, child_path
        yield from _iter_nodes(child, child_path)


def _node_entry(node: Node, parent: Node, path: list[str], color: str, reason: str) -> dict[str, Any]:
    stats = node.stats.to_dict()
    return {
        "opponent_color": color,
        "path": path,
        "line": _line_text(path),
        "fen": node.fen,
        "games": stats["games"],
        "share_of_parent": _pct(node.stats.n, parent.stats.n),
        "score_pct": stats["score_pct"],
        "expected_pct": stats["expected_pct"],
        "perf_delta": stats["perf_delta"],
        "shrunk_delta": stats["shrunk_delta"],
        "avg_eval_cp": stats["avg_eval_cp"],
        "early_loss_rate": stats["early_loss_rate"],
        "reason": reason,
    }


def find_steer_points(trees: dict[str, Node], min_games: int = 3) -> tuple[list[dict], list[dict]]:
    """Positions (after *your* move) where they underperform / overperform.

    Only nodes reached by the non-scouted side's move are actionable: those are
    the choices you control. Nested duplicates are collapsed so a weak line isn't
    listed once per ply.
    """
    weak: list[tuple[float, dict]] = []
    strong: list[tuple[float, dict]] = []
    for color, root in trees.items():
        for node, parent, path in _iter_nodes(root):
            if node.stats.n < min_games or _mover_is_scouted(node.ply, color):
                continue
            stats = node.stats.to_dict()
            shrunk = node.stats.shrunk
            eval_cp = stats["avg_eval_cp"]
            # Eval (their POV) nudges the ranking when the engine pass ran.
            eval_term = (eval_cp / 1000) if eval_cp is not None else 0.0
            weakness = -shrunk - eval_term * 0.5
            if (shrunk <= -0.05 or (eval_cp is not None and eval_cp <= -60)) and stats["score_pct"] < 55:
                bits = [f"they score {stats['score_pct']:.0f}%"]
                if stats["expected_pct"] is not None:
                    bits.append(f"vs {stats['expected_pct']:.0f}% expected")
                if eval_cp is not None:
                    bits.append(f"avg eval at move 12 {eval_cp / 100:+.1f}")
                weak.append((weakness, _node_entry(node, parent, path, color, ", ".join(bits))))
            elif shrunk >= 0.06 and stats["score_pct"] >= 55:
                bits = [f"they score {stats['score_pct']:.0f}%"]
                if stats["expected_pct"] is not None:
                    bits.append(f"vs {stats['expected_pct']:.0f}% expected")
                strong.append((-weakness, _node_entry(node, parent, path, color, ", ".join(bits))))

    def dedupe(items: list[tuple[float, dict]], limit: int) -> list[dict]:
        out: list[dict] = []
        for _score, entry in sorted(items, key=lambda x: -x[0]):
            if any(
                entry["opponent_color"] == kept["opponent_color"]
                and (entry["path"][: len(kept["path"])] == kept["path"] or kept["path"][: len(entry["path"])] == entry["path"])
                for kept in out
            ):
                continue
            out.append(entry)
            if len(out) >= limit:
                break
        return out

    return dedupe(weak, 8), dedupe(strong, 6)


def find_decision_points(trees: dict[str, Node], baseline_time: float | None, min_games: int = 3) -> list[dict]:
    """Positions where *they* are to move and look unsure.

    Signals: no dominant reply (top choice < 55%) or they burn clearly more clock
    than usual on the move here. These are positions their preparation runs out.
    """
    out = []
    for color, root in trees.items():
        for node, _parent, path in _iter_nodes(root):
            if node.stats.n < min_games or not _mover_is_scouted(node.ply + 1, color) or node.ply >= TREE_MAX_PLIES:
                continue
            replies = sorted(node.children.values(), key=lambda c: -c.stats.n)
            if not replies:
                continue
            top_share = replies[0].stats.n / node.stats.n
            spent = [t for c in replies for t in c.time_pcts]
            avg_spent = mean(spent) if spent else None
            slow = avg_spent is not None and baseline_time and avg_spent >= max(1.5, baseline_time * 2.5)
            scattered = top_share < 0.55 and len(replies) >= 2
            if not (slow or scattered):
                continue
            reasons = []
            if scattered:
                reasons.append(f"no settled reply ({len(replies)} different moves, top one {top_share * 100:.0f}%)")
            if slow:
                reasons.append(f"spends {avg_spent:.1f}% of their clock on this move (usual {baseline_time:.1f}%)")
            stats = node.stats.to_dict()
            out.append({
                "opponent_color": color,
                "path": path,
                "line": _line_text(path),
                "fen": node.fen,
                "games": node.stats.n,
                "score_pct": stats["score_pct"],
                "perf_delta": stats["perf_delta"],
                "replies": [
                    {"san": c.san, "games": c.stats.n, "score_pct": c.stats.to_dict()["score_pct"]}
                    for c in replies[:4]
                ],
                "avg_time_pct": round(avg_spent, 2) if avg_spent is not None else None,
                "reason": "; ".join(reasons),
                "_rank": node.stats.n * (1.5 if slow and scattered else 1.0) * (1 - top_share + (0.4 if slow else 0)),
            })
    out.sort(key=lambda item: -item["_rank"])
    for item in out:
        item.pop("_rank", None)
    return out[:8]


def _modal_line(games: list[ScoutGame], max_plies: int = TREE_MAX_PLIES) -> tuple[list[str], int]:
    """Most common move order among ``games`` (greedy), and how many follow it all the way."""
    line: list[str] = []
    pool = games
    for ply in range(max_plies):
        counter = Counter(g.sans[ply] for g in pool if len(g.sans) > ply)
        if not counter:
            break
        san, count = counter.most_common(1)[0]
        if count < 2:
            break
        line.append(san)
        pool = [g for g in pool if len(g.sans) > ply and g.sans[ply] == san]
    return line, len(pool)


def familiarity(stats: Stats, color_total: int, baseline_time: float | None) -> dict[str, Any]:
    n = stats.n
    share = n / color_total if color_total else 0
    volume = 0.5 * min(1.0, share / 0.35) + 0.5 * min(1.0, n / 15)
    depth = _avg(g.book_depth for g in stats.games) or 0.0
    depth_norm = min(1.0, depth / 7)
    fam_time = _avg(g.opening_time_pct for g in stats.games)
    if fam_time is not None and baseline_time:
        speed_norm = max(0.0, min(1.0, 1.5 - fam_time / baseline_time))
    else:
        speed_norm = 0.5
    value = round(100 * (0.45 * volume + 0.35 * depth_norm + 0.20 * speed_norm))
    label = "Main weapon" if value >= 70 else "Comfortable" if value >= 45 else "Occasional" if value >= 25 else "Rarely seen"
    return {
        "score": value,
        "label": label,
        "components": {
            "volume": round(volume * 100),
            "book_depth": round(depth_norm * 100),
            "speed": round(speed_norm * 100),
        },
    }


def _family_rows(games: list[ScoutGame], color: str, baseline_time: float | None) -> list[dict]:
    mine = [g for g in games if g.color == color]
    groups: dict[str, Stats] = defaultdict(Stats)
    for g in mine:
        groups[g.family].add(g)
    rows = []
    for family, stats in groups.items():
        variations: dict[str, Stats] = defaultdict(Stats)
        for g in stats.games:
            variations[g.variation or "Main line"].add(g)
        line, followers = _modal_line(stats.games)
        rows.append({
            "family": family,
            "eco": Counter(g.eco for g in stats.games).most_common(1)[0][0],
            **stats.to_dict(total=len(mine)),
            "familiarity": familiarity(stats, len(mine), baseline_time),
            "main_line": _line_text(line),
            "main_line_path": line,
            "main_line_games": followers,
            "variations": sorted(
                ({"variation": name, **vstats.to_dict(total=stats.n)} for name, vstats in variations.items()),
                key=lambda row: -row["games"],
            )[:8],
            "recent_games": [
                {"date": g.date, "url": g.url, "foe": g.foe, "result": g.result, "variation": g.variation,
                 "own_rating": g.own_rating, "foe_rating": g.foe_rating}
                for g in sorted(stats.games, key=lambda g: -g.end_time)[:6]
            ],
        })
    rows.sort(key=lambda row: (-row["games"], row["family"]))
    return rows


def _move_groups(games: list[ScoutGame], index: int) -> dict[str, Stats]:
    groups: dict[str, Stats] = defaultdict(Stats)
    for g in games:
        if len(g.sans) > index:
            groups[g.sans[index]].add(g)
    return groups


def _as_white(games: list[ScoutGame]) -> dict[str, Any]:
    whites = [g for g in games if g.color == "white"]
    first = _move_groups(whites, 0)
    rows = []
    for move, stats in sorted(first.items(), key=lambda kv: -kv[1].n):
        replies = _move_groups(stats.games, 1)
        rows.append({
            "move": move,
            **stats.to_dict(total=len(whites)),
            "replies": [
                {"move": reply, **rstats.to_dict(total=stats.n)}
                for reply, rstats in sorted(replies.items(), key=lambda kv: -kv[1].n)[:8]
            ],
        })
    return {"games": len(whites), "first_moves": rows}


def _as_black(games: list[ScoutGame]) -> dict[str, Any]:
    blacks = [g for g in games if g.color == "black"]
    first = _move_groups(blacks, 0)
    rows = []
    for move, stats in sorted(first.items(), key=lambda kv: -kv[1].n):
        replies = _move_groups(stats.games, 1)
        fams: dict[str, Stats] = defaultdict(Stats)
        for g in stats.games:
            fams[g.family].add(g)
        rows.append({
            "move": move,
            **stats.to_dict(total=len(blacks)),
            "replies": [
                {"move": reply, **rstats.to_dict(total=stats.n)}
                for reply, rstats in sorted(replies.items(), key=lambda kv: -kv[1].n)[:8]
            ],
            "families": [
                {"family": fam, **fstats.to_dict(total=stats.n)}
                for fam, fstats in sorted(fams.items(), key=lambda kv: -kv[1].n)[:6]
            ],
        })
    return {"games": len(blacks), "vs_first_moves": rows}


def _profile(games: list[ScoutGame]) -> dict[str, Any]:
    overall = Stats()
    by_color = {"white": Stats(), "black": Stats()}
    for g in games:
        overall.add(g)
        by_color[g.color].add(g)

    ratings: dict[str, int] = {}
    for g in sorted(games, key=lambda g: g.end_time):
        if g.time_class and g.own_rating:
            ratings[g.time_class] = g.own_rating

    terminations: dict[str, Counter] = {"win": Counter(), "loss": Counter(), "draw": Counter()}
    for g in games:
        bucket, _, reason = g.result_reason.partition(":")
        terminations[bucket][reason] += 1

    def term_rows(counter: Counter) -> list[dict]:
        total = sum(counter.values())
        return [{"reason": r, "games": c, "pct": _pct(c, total)} for r, c in counter.most_common()]

    long_games = Stats()
    short_games = Stats()
    for g in games:
        (long_games if g.full_moves > 40 else short_games).add(g)

    time_classes = Counter(g.time_class for g in games if g.time_class)

    return {
        "games": len(games),
        "ratings": ratings,
        "time_classes": dict(time_classes.most_common()),
        "overall": overall.to_dict(),
        "white": by_color["white"].to_dict(total=len(games)),
        "black": by_color["black"].to_dict(total=len(games)),
        "avg_game_length": _avg(g.full_moves for g in games),
        "terminations": {k: term_rows(v) for k, v in terminations.items()},
        "long_games": long_games.to_dict(total=len(games)),
        "short_games": short_games.to_dict(total=len(games)),
        "clock_games": sum(1 for g in games if g.opening_time_pct is not None),
    }


def _recent_changes(games: list[ScoutGame]) -> list[dict]:
    """Openings whose share jumped in their most recent quarter of games (new prep)."""
    out = []
    for color in ("white", "black"):
        mine = sorted((g for g in games if g.color == color), key=lambda g: -g.end_time)
        if len(mine) < 16:
            continue
        cut = max(6, len(mine) // 4)
        recent, earlier = mine[:cut], mine[cut:]
        r_count = Counter(g.family for g in recent)
        e_count = Counter(g.family for g in earlier)
        for fam, count in r_count.items():
            r_share = count / len(recent)
            e_share = e_count.get(fam, 0) / len(earlier)
            if count >= 3 and r_share - e_share >= 0.15:
                out.append({"color": color, "family": fam, "recent_share": _pct(count, len(recent)),
                            "earlier_share": _pct(e_count.get(fam, 0), len(earlier)), "direction": "new",
                            "recent_games": len(recent)})
        for fam, count in e_count.items():
            e_share = count / len(earlier)
            r_share = r_count.get(fam, 0) / len(recent)
            if count >= 5 and e_share - r_share >= 0.2:
                out.append({"color": color, "family": fam, "recent_share": _pct(r_count.get(fam, 0), len(recent)),
                            "earlier_share": _pct(count, len(earlier)), "direction": "dropped",
                            "recent_games": len(recent)})
    return out


def _fmt_move(move: str, color_moving: str) -> str:
    return f"1.{move}" if color_moving == "white" else f"1...{move}"


def _game_plan(report: dict[str, Any]) -> dict[str, list[str]]:
    """Plain-language takeaways assembled from the computed sections."""
    plan: dict[str, list[str]] = {"you_white": [], "you_black": [], "general": []}
    name = report["username"]

    # ── You are White (they are Black) ──
    vs = [row for row in report["as_black"]["vs_first_moves"] if row["games"] >= 3]
    if vs:
        best = min(vs, key=lambda r: r["shrunk_delta"])
        worst = max(vs, key=lambda r: r["shrunk_delta"])
        line = f"Open {_fmt_move(best['move'], 'white')}: {name} scores {best['score_pct']:.0f}% against it"
        if best["expected_pct"] is not None:
            line += f" (rating-expected {best['expected_pct']:.0f}%)"
        plan["you_white"].append(line + f" over {best['games']} games.")
        if worst is not best and worst["shrunk_delta"] > 3:
            plan["you_white"].append(
                f"Avoid {_fmt_move(worst['move'], 'white')} if you can — they over-perform against it "
                f"({worst['score_pct']:.0f}% vs {worst['expected_pct'] or 50:.0f}% expected)."
            )
        if best["families"]:
            top = best["families"][0]
            plan["you_white"].append(
                f"After {_fmt_move(best['move'], 'white')} expect the {top['family']} ({top['frequency']:.0f}% of the time)."
            )
    black_fams = [f for f in report["families"]["black"] if f["games"] >= 3]
    if black_fams:
        weak = min(black_fams, key=lambda f: f["shrunk_delta"])
        if weak["shrunk_delta"] < -2:
            plan["you_white"].append(
                f"Their weakest defence is the {weak['family']}: {weak['score_pct']:.0f}% score"
                + (f" (expected {weak['expected_pct']:.0f}%)" if weak["expected_pct"] is not None else "")
                + f" in {weak['games']} games"
                + (f", avg eval at move 12 {weak['avg_eval_cp'] / 100:+.1f}" if weak["avg_eval_cp"] is not None else "")
                + "."
            )

    # ── You are Black (they are White) ──
    firsts = report["as_white"]["first_moves"]
    if firsts:
        main = firsts[0]
        plan["you_black"].append(
            f"Prepare for {_fmt_move(main['move'], 'white')} — they play it in {main['frequency']:.0f}% of their White games."
        )
        replies = [r for r in main["replies"] if r["games"] >= 3]
        if replies:
            best_reply = min(replies, key=lambda r: r["shrunk_delta"])
            if best_reply["shrunk_delta"] < -2:
                exp = f" vs {best_reply['expected_pct']:.0f}% expected" if best_reply["expected_pct"] is not None else ""
                plan["you_black"].append(
                    f"Answer with {_fmt_move(main['move'], 'white')} {best_reply['move']}: they score "
                    f"{best_reply['score_pct']:.0f}%{exp} against it ({best_reply['games']} games)."
                )
            worst_reply = max(replies, key=lambda r: r["shrunk_delta"])
            if worst_reply is not best_reply and worst_reply["shrunk_delta"] > 3:
                plan["you_black"].append(
                    f"Be careful with 1...{worst_reply['move']} — they score {worst_reply['score_pct']:.0f}% against it."
                )
    white_fams = [f for f in report["families"]["white"] if f["games"] >= 3]
    if white_fams:
        known = max(white_fams, key=lambda f: f["familiarity"]["score"])
        plan["you_black"].append(
            f"Their most familiar territory as White is the {known['family']} (familiarity {known['familiarity']['score']}/100"
            + (f", follows their own move order ~{known['avg_book_depth']:.0f} moves deep" if known["avg_book_depth"] else "")
            + ")."
        )

    for entry in report["steer_into"][:2]:
        key = "you_white" if entry["opponent_color"] == "black" else "you_black"
        plan[key].append(f"Steer into {entry['line']} — {entry['reason']}.")

    # ── General habits ──
    prof = report["profile"]
    losses = {row["reason"]: row for row in prof["terminations"]["loss"]}
    total_losses = sum(row["games"] for row in prof["terminations"]["loss"])
    if total_losses >= 5 and losses.get("time", {}).get("pct", 0) >= 25:
        plan["general"].append(
            f"{losses['time']['pct']:.0f}% of their losses are on time — keep the position complex and make them use the clock."
        )
    early = prof["overall"]["early_loss_rate"]
    if prof["games"] >= 20 and early >= 12:
        plan["general"].append(f"{early:.0f}% of their games end in a loss within {EARLY_LOSS_MOVES} moves — they can collapse early under pressure.")
    lg, sg = prof["long_games"], prof["short_games"]
    if lg["games"] >= 8 and sg["games"] >= 8 and lg["shrunk_delta"] - sg["shrunk_delta"] <= -6:
        plan["general"].append(
            f"They score {lg['score_pct']:.0f}% in games past move 40 vs {sg['score_pct']:.0f}% in shorter ones — keep pieces on and grind."
        )
    elif lg["games"] >= 8 and sg["games"] >= 8 and lg["shrunk_delta"] - sg["shrunk_delta"] >= 6:
        plan["general"].append(
            f"They get stronger in long games ({lg['score_pct']:.0f}% past move 40) — look for your chances early."
        )
    white, black = prof["white"], prof["black"]
    if white["games"] >= 8 and black["games"] >= 8 and abs(white["score_pct"] - black["score_pct"]) >= 10:
        weaker = "Black" if black["score_pct"] < white["score_pct"] else "White"
        plan["general"].append(
            f"Clearly weaker with {weaker} ({min(white['score_pct'], black['score_pct']):.0f}% vs {max(white['score_pct'], black['score_pct']):.0f}%)."
        )
    eval_avg = prof["overall"]["avg_eval_cp"]
    if eval_avg is not None and prof["overall"]["evaluated_games"] >= 10:
        if eval_avg <= -40:
            plan["general"].append(f"They usually leave the opening worse (avg {eval_avg / 100:+.1f} at move 12) — opening prep pays off against them.")
        elif eval_avg >= 40:
            plan["general"].append(f"They usually leave the opening better (avg {eval_avg / 100:+.1f} at move 12) — don't expect to out-prepare them; aim for the middlegame.")
    for change in report["recent_changes"][:2]:
        side = "White" if change["color"] == "white" else "Black"
        if change["direction"] == "new":
            plan["general"].append(
                f"New as {side}: the {change['family']} — {change['recent_share']:.0f}% of their last {change['recent_games']} games (was {change['earlier_share']:.0f}%)."
            )
        else:
            plan["general"].append(
                f"Dropped as {side}: the {change['family']} — down to {change['recent_share']:.0f}% recently (was {change['earlier_share']:.0f}%)."
            )
    return plan


def shrunk_score_pct(stats: Stats, k: int = SHRINK_K) -> float:
    """Your score %, pulled toward 50% by ``k`` pseudo-draws so 2/2 isn't "100%"."""
    return (sum(g.score for g in stats.games) + 0.5 * k) / (stats.n + k) * 100


def _matchup(report: dict[str, Any], my_games: list[ScoutGame], my_name: str) -> dict[str, Any]:
    """Cross their repertoire with yours: which of your lines hit their weak spots."""
    my_white = [g for g in my_games if g.color == "white"]
    my_black = [g for g in my_games if g.color == "black"]

    my_white_fam: dict[str, Stats] = defaultdict(Stats)
    for g in my_white:
        my_white_fam[g.family].add(g)
    my_black_fam: dict[str, Stats] = defaultdict(Stats)
    for g in my_black:
        my_black_fam[g.family].add(g)

    # You as White: for each first move you play, where would they take the game?
    as_white = []
    my_first = _move_groups(my_white, 0)
    their_vs = {row["move"]: row for row in report["as_black"]["vs_first_moves"]}
    for move, stats in sorted(my_first.items(), key=lambda kv: -kv[1].n):
        if stats.n < 3:
            continue
        their = their_vs.get(move)
        likely = []
        weighted_you = 0.0
        weight = 0.0
        if their:
            for fam in their["families"][:4]:
                yours = my_white_fam.get(fam["family"])
                your_score = yours.to_dict()["score_pct"] if yours and yours.n >= 2 else None
                likely.append({"family": fam["family"], "their_share": fam["frequency"], "their_score_pct": fam["score_pct"],
                               "your_games": yours.n if yours else 0, "your_score_pct": your_score})
                if your_score is not None:
                    weighted_you += shrunk_score_pct(yours) * fam["games"]
                    weight += fam["games"]
        your_stats = stats.to_dict(total=len(my_white))
        their_delta = their["shrunk_delta"] if their else 0.0
        your_in_lines = weighted_you / weight if weight else shrunk_score_pct(stats)
        as_white.append({
            "move": move,
            "your_games": stats.n,
            "your_score_pct": your_stats["score_pct"],
            "their_games": their["games"] if their else 0,
            "their_score_pct": their["score_pct"] if their else None,
            "their_shrunk_delta": their_delta,
            "likely_lines": likely,
            "edge": round((your_in_lines - 50) - their_delta, 1),
        })
    as_white.sort(key=lambda row: -row["edge"])

    # You as Black: vs each first move they play, which of your defences fares best?
    as_black = []
    their_first = {row["move"]: row for row in report["as_white"]["first_moves"]}
    my_vs = defaultdict(lambda: defaultdict(Stats))
    for g in my_black:
        if len(g.sans) >= 2:
            my_vs[g.sans[0]][g.sans[1]].add(g)
    for move, their in their_first.items():
        if their["games"] < 3:
            continue
        their_replies = {r["move"]: r for r in their["replies"]}
        options = []
        for reply, stats in sorted(my_vs.get(move, {}).items(), key=lambda kv: -kv[1].n):
            if stats.n < 2:
                continue
            your = stats.to_dict()
            vs_them = their_replies.get(reply)
            their_delta = vs_them["shrunk_delta"] if vs_them else 0.0
            options.append({
                "reply": reply,
                "your_games": stats.n,
                "your_score_pct": your["score_pct"],
                "their_games": vs_them["games"] if vs_them else 0,
                "their_score_pct": vs_them["score_pct"] if vs_them else None,
                "edge": round((shrunk_score_pct(stats) - 50) - their_delta, 1),
            })
        options.sort(key=lambda row: -row["edge"])
        as_black.append({"their_move": move, "their_share": their["frequency"], "options": options[:5]})

    return {"username": my_name, "games": len(my_games), "you_white": as_white[:6], "you_black": as_black[:4]}


def _safe_section(name: str, build: Any) -> Any:
    """Optional report sections must never take the whole report down."""
    try:
        return build()
    except Exception:
        logger.warning("Scout section %s failed", name, exc_info=True)
        return None


def build_scouting_report(
    username: str,
    raw_games: list[dict[str, Any]],
    *,
    filters: dict[str, Any] | None = None,
    evaluator: Any = None,
    my_username: str | None = None,
    my_raw_games: list[dict[str, Any]] | None = None,
    tz_offset_minutes: int = 0,
) -> dict[str, Any]:
    """Pure (given ``evaluator``) report builder.

    ``evaluator`` is an optional callable ``(list[ScoutGame]) -> dict`` that
    fills ``eval_cp`` on games in place and returns engine metadata. Tests pass
    a fake; production passes ``_engine_evals``.
    """
    games = [g for g in (parse_game(raw, username) for raw in raw_games) if g is not None]
    games.sort(key=lambda g: -g.end_time)

    engine_meta: dict[str, Any] = {"enabled": False}
    if evaluator is not None and games:
        try:
            engine_meta = {"enabled": True, **evaluator(games)}
        except Exception as exc:  # engine trouble must not kill the report
            logger.warning("Scout engine pass failed", exc_info=True)
            engine_meta = {"enabled": True, "available": False, "error": str(exc)[:200]}

    trees = {"white": build_tree(games, "white"), "black": build_tree(games, "black")}
    assign_book_depth(games, trees)

    clock_moves = [t for g in games for t in g.move_time_pct[:20] if t is not None]
    baseline_move_time = mean(clock_moves) if clock_moves else None
    baseline_opening_time = _avg(g.opening_time_pct for g in games)

    steer_into, avoid = find_steer_points(trees)

    report: dict[str, Any] = {
        "username": username,
        "filters": filters or {},
        "profile": _profile(games),
        "baseline": {
            "avg_move_time_pct": round(baseline_move_time, 2) if baseline_move_time else None,
            "avg_opening_time_pct": baseline_opening_time,
        },
        "families": {
            "white": _family_rows(games, "white", baseline_opening_time),
            "black": _family_rows(games, "black", baseline_opening_time),
        },
        "as_white": _as_white(games),
        "as_black": _as_black(games),
        "tree": {
            "white": serialize_tree(trees["white"], "white"),
            "black": serialize_tree(trees["black"], "black"),
        },
        "steer_into": steer_into,
        "avoid": avoid,
        "decision_points": find_decision_points(trees, baseline_move_time),
        "recent_changes": _recent_changes(games),
        "engine": engine_meta,
        "matchup": None,
    }
    # Local import: scout_habits imports helpers from this module.
    from .scout_habits import build_habits, build_head_to_head

    report["habits"] = _safe_section("habits", lambda: build_habits(raw_games, username, tz_offset_minutes=tz_offset_minutes))
    report["head_to_head"] = (
        _safe_section("head_to_head", lambda: build_head_to_head(raw_games, username, my_username))
        if my_username and my_username.casefold() != username.casefold()
        else None
    )
    report["game_plan"] = _game_plan(report)
    # Surface the strongest habit / head-to-head findings in the plan too.
    for extra in ((report["habits"] or {}).get("insights") or [])[:3]:
        if extra not in report["game_plan"]["general"]:
            report["game_plan"]["general"].append(extra)
    for extra in ((report["head_to_head"] or {}).get("insights") or [])[:1]:
        report["game_plan"]["general"].insert(0, extra)

    if my_username and my_raw_games is not None:
        mine = [g for g in (parse_game(raw, my_username) for raw in my_raw_games) if g is not None]
        if mine:
            report["matchup"] = _matchup(report, mine, my_username)
    return report


# ── impure edges ──────────────────────────────────────────────────────────────

_EVAL_CACHE: dict[tuple[str, int], float] = {}
_EVAL_CACHE_LOCK = threading.Lock()
_EVAL_CACHE_MAX = 20000


def _engine_evals(games: list[ScoutGame], *, depth: int = 10, max_games: int = 200) -> dict[str, Any]:
    """Score the move-12 position of each game with Stockfish (their POV)."""
    from stockfish_engine import StockfishEngine  # root-level module

    targets = [g for g in games if g.fen_at_eval][:max_games]
    pending = []
    for g in targets:
        with _EVAL_CACHE_LOCK:
            cached = _EVAL_CACHE.get((g.fen_at_eval, depth))  # type: ignore[arg-type]
        if cached is not None:
            g.eval_cp = cached if g.color == "white" else -cached
        else:
            pending.append(g)

    if pending:
        with StockfishEngine(depth=depth) as engine:
            for g in pending:
                board = chess.Board(g.fen_at_eval)  # type: ignore[arg-type]
                cp, _best, _pv = engine.analyse_position(board, depth=depth, include_pv=False)
                if cp is None:
                    continue
                white_pov = float(cp) if board.turn == chess.WHITE else -float(cp)
                white_pov = max(-EVAL_CLIP_CP * 2, min(EVAL_CLIP_CP * 2, white_pov))
                with _EVAL_CACHE_LOCK:
                    if len(_EVAL_CACHE) >= _EVAL_CACHE_MAX:
                        _EVAL_CACHE.clear()
                    _EVAL_CACHE[(g.fen_at_eval, depth)] = white_pov  # type: ignore[index]
                g.eval_cp = white_pov if g.color == "white" else -white_pov

    return {
        "available": True,
        "depth": depth,
        "eval_ply": EVAL_PLY,
        "evaluated_games": sum(1 for g in targets if g.eval_cp is not None),
    }


@ttl_lru_cache(maxsize=16, ttl_seconds=600)
def get_scouting_report(
    username: str,
    limit: int = 300,
    time_class: str | None = None,
    rated_only: bool = False,
    engine: bool = False,
    me: str | None = None,
    tz_offset: int = 0,
) -> dict[str, Any]:
    username = username.strip()
    limit = max(20, min(limit, 500))
    raw = get_recent_games(username, limit=limit)
    if time_class:
        raw = [g for g in raw if g.get("time_class") == time_class]
    if rated_only:
        raw = [g for g in raw if g.get("rated")]

    my_raw = None
    me = (me or "").strip() or None
    if me and me.casefold() != username.casefold():
        try:
            my_raw = get_recent_games(me, limit=300)
            if time_class:
                my_raw = [g for g in my_raw if g.get("time_class") == time_class]
        except Exception:
            logger.warning("Could not load the requesting player's games for the matchup", exc_info=True)
            my_raw = None

    return build_scouting_report(
        username,
        raw,
        filters={"limit": limit, "time_class": time_class, "rated_only": rated_only, "engine": engine, "me": me,
                 "tz_offset": tz_offset},
        evaluator=_engine_evals if engine else None,
        my_username=me,
        my_raw_games=my_raw,
        tz_offset_minutes=tz_offset,
    )
