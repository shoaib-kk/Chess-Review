"""Engine-free habit analysis for the opponent scout (``report.habits``) and the
head-to-head section (``report.head_to_head``).

Everything is from the scouted player's point of view unless noted. Scores,
expectations and deltas follow ``opponent_scout.Stats.to_dict``: percentages
0-100, ``perf_delta`` in percentage points of (score - Elo expectation), and
``shrunk_delta`` pulled toward 0 with ``shrunk_delta`` (k = 5 pseudo-games).

Feature definitions (``positions``; each game is replayed once, ply = half move):

* ``queenless``: no queens on the board after move 25 (ply 50) AND the game
  lasted at least 5 more full moves (>= 60 plies).
* ``opposite_castling`` / ``same_side_castling``: both players castled, on
  different / the same wing (kingside vs queenside).
* ``open_center``: after move 15 (ply 30) at most 2 pawns in total on the d and
  e files. ``closed_center``: not open, and >= 2 locked pawn pairs (a white pawn
  directly blocked by a black pawn) on the c-f files after move 15.
* ``isolated_queen_pawn``: THEY have a d-pawn with no friendly pawn on the c or
  e file at the end of any move from 15 to 20 (plies 30-40).
* ``bishop_pair_for`` / ``bishop_pair_against``: at move 25 (ply 50) they (or
  the opponent) have two bishops and the other side does not.
* Endgame types: an endgame starts at the first position (ply >= 20, stable for
  two plies) where BOTH sides have <= 13 points of non-pawn material
  (N3 B3 R5 Q9). Its type: ``queen_endgame`` if any queen remains,
  else ``rook_endgame`` if any rook, else ``minor_piece_endgame`` if any
  knight/bishop, else ``pawn_endgame``. Only the first type reached counts.

Resignation / material (piece values P1 N3 B3 R5 Q9, sampled after each ply and
smoothed so the instant between a capture and its recapture is ignored):

* ``resignations`` = games they lost by resigning; ``resigned_not_behind`` =
  those where material was level or better for them at the end; the pct uses
  ``resignations`` as the denominator. ``avg_material_at_resign`` is their
  average material balance at the end of those games.
* ``played_on_lost`` = losses by checkmate or timeout where they were 5+ points
  down at some point in the last 10 plies; pct denominator = their mate/time losses.
* ``comebacks`` = games won or drawn after being 3+ down at some point; rate
  denominator = games in which they were ever 3+ down.
* ``collapses_from_ahead`` = games lost after being 3+ up at some point; rate
  denominator = games in which they were ever 3+ up.
"""

from __future__ import annotations

import io
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Any

import chess
import chess.pgn

from .opponent_scout import (
    DRAW_CODES,
    expected_score,
    opening_from_eco_url,
    shrunk_delta,
    split_opening,
)

SESSION_GAP_MINUTES = 30
MIN_SPLIT_GAMES = 8        # minimum sample before an insight may mention a split
MIN_ABS_SHRUNK = 4.0       # ... and its |shrunk_delta| must be at least this (pp)
H2H_LINE_PLIES = 8

_pc = int.bit_count if hasattr(int, "bit_count") else (lambda x: bin(x).count("1"))

_FILE_DE = chess.BB_FILE_D | chess.BB_FILE_E
_FILE_CF = chess.BB_FILE_C | chess.BB_FILE_D | chess.BB_FILE_E | chess.BB_FILE_F

POSITION_DEFS: dict[str, tuple[str, str]] = {
    "queenless": ("Queenless middlegames", "Both queens are off the board after move 25 and the game lasted at least 5 more moves."),
    "opposite_castling": ("Opposite-side castling games", "The two players castled on opposite wings (one kingside, one queenside)."),
    "same_side_castling": ("Same-side castling games", "Both players castled on the same wing."),
    "open_center": ("Open-centre positions", "After move 15 there are at most 2 pawns in total on the d and e files."),
    "closed_center": ("Closed-centre positions", "After move 15 the centre is not open and at least 2 pawn pairs are locked head to head on the c-f files."),
    "isolated_queen_pawn": ("Isolated queen's pawn (theirs)", "They have a d-pawn with no friendly pawns on the c or e files at some point between moves 15 and 20."),
    "bishop_pair_for": ("Positions where they have the bishop pair", "At move 25 they have both bishops and the opponent does not."),
    "bishop_pair_against": ("Positions where you have the bishop pair", "At move 25 the opponent has both bishops and they do not."),
    "rook_endgame": ("Rook endgames", "First endgame reached (both sides at most 13 points of non-pawn material) has rooks and no queens."),
    "minor_piece_endgame": ("Minor-piece endgames", "First endgame reached (both sides at most 13 points of non-pawn material) has only knights/bishops besides pawns."),
    "pawn_endgame": ("Pawn endgames", "First endgame reached (both sides at most 13 points of non-pawn material) has only kings and pawns."),
    "queen_endgame": ("Queen endgames", "First endgame reached (both sides at most 13 points of non-pawn material) still has a queen on the board."),
}

TOD_BUCKETS = [("night", "Night (0-6)"), ("morning", "Morning (6-12)"), ("afternoon", "Afternoon (12-18)"), ("evening", "Evening (18-24)")]
TOD_PHRASE = {
    "night": "late at night (midnight to 6am, local time)",
    "morning": "in the morning (6am-noon, local time)",
    "afternoon": "in the afternoon (noon-6pm, local time)",
    "evening": "in the evening (6pm-midnight, local time)",
}
WEEKDAYS = [("mon", "Monday"), ("tue", "Tuesday"), ("wed", "Wednesday"), ("thu", "Thursday"), ("fri", "Friday"), ("sat", "Saturday"), ("sun", "Sunday")]
SESSION_INDEX = [("1", "1st game"), ("2", "2nd game"), ("3", "3rd game"), ("4-5", "4th-5th game"), ("6+", "6th game or later")]


# ── helpers ───────────────────────────────────────────────────────────────────


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def _own_score(code: str | None) -> float:
    if code == "win":
        return 1.0
    if code in DRAW_CODES:
        return 0.5
    return 0.0


def _int(raw: Any) -> int | None:
    try:
        return int(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _result_word(score: float) -> str:
    return "win" if score == 1 else "draw" if score == 0.5 else "loss"


def _split(key: str, label: str, items: list[tuple[float, float | None]]) -> dict[str, Any]:
    """ScoutSplit from ``(score, expected)`` tuples. Every key present even when empty."""
    n = len(items)
    rated = [(s, e) for s, e in items if e is not None]
    s_sum = sum(s for s, _ in rated)
    e_sum = sum(e for _, e in rated)
    return {
        "key": key,
        "label": label,
        "games": n,
        "score_pct": _pct(sum(s for s, _ in items), n),
        "expected_pct": _pct(e_sum, len(rated)) if rated else None,
        "perf_delta": round((s_sum - e_sum) / len(rated) * 100, 1) if rated else None,
        "shrunk_delta": round(shrunk_delta(s_sum, e_sum, len(rated)) * 100, 1),
    }


def _line_text(sans: list[str]) -> str:
    parts = []
    for i, san in enumerate(sans):
        parts.append(f"{i // 2 + 1}. {san}" if i % 2 == 0 else san)
    return " ".join(parts)


@dataclass
class _Game:
    white: bool
    score: float
    expected: float | None
    own_code: str | None
    own_rating: int | None
    foe_rating: int | None
    end_time: int
    pgn: str
    features: set[str] = field(default_factory=set)
    replayed: bool = False
    final_mat: int = 0
    min_def: int = 0        # worst smoothed material balance (their POV), <= 0
    max_lead: int = 0       # best smoothed material balance, >= 0
    tail_min: int = 0       # worst smoothed balance in the last 10 plies
    pair: tuple[float, float | None] = (0.0, None)


def _parse(raw: dict[str, Any], username: str) -> _Game | None:
    target = username.casefold()
    if (raw.get("white_username") or "").casefold() == target:
        white = True
    elif (raw.get("black_username") or "").casefold() == target:
        white = False
    else:
        return None
    if raw.get("rules") not in (None, "chess"):
        return None
    own_code = raw.get("white_result" if white else "black_result")
    pgn = raw.get("pgn") or ""
    own_rating = foe_rating = None
    if pgn:
        # cheap header scrape; full replay happens once, later
        try:
            headers = chess.pgn.read_headers(io.StringIO(pgn))
        except Exception:
            headers = None
        if headers is not None:
            own_rating = _int(headers.get("WhiteElo" if white else "BlackElo"))
            foe_rating = _int(headers.get("BlackElo" if white else "WhiteElo"))
    score = _own_score(own_code)
    expected = expected_score(own_rating, foe_rating)
    g = _Game(white, score, expected, own_code, own_rating, foe_rating, int(raw.get("end_time") or 0), pgn)
    g.pair = (score, expected)
    return g


# ── single-pass replay ────────────────────────────────────────────────────────


def _smooth(d: list[int]) -> tuple[list[int], list[int]]:
    """Per-ply (low, high) balances ignoring the instant between a capture and recapture."""
    n = len(d)
    low = [max(d[i], d[i + 1]) for i in range(n - 1)] + [d[-1]]
    high = [min(d[i], d[i + 1]) for i in range(n - 1)] + [d[-1]]
    return low, high


def _replay(game: _Game) -> None:
    try:
        pgn_game = chess.pgn.read_game(io.StringIO(game.pgn))
    except Exception:
        return
    if pgn_game is None:
        return
    board = pgn_game.board()
    if board.fen() != chess.STARTING_FEN:
        return

    N, B, R, Q, P = chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.PAWN
    W, K = chess.WHITE, chess.BLACK
    me = W if game.white else K
    you = not me
    mask = board.pieces_mask
    feats: set[str] = set()
    castled: dict[bool, str] = {}
    mat: list[int] = []            # white minus black, one entry per ply
    endgame_prev: str | None = None
    endgame: str | None = None
    ply = 0

    for move in pgn_game.mainline_moves():
        try:
            if board.is_castling(move):
                castled[board.turn] = "k" if chess.square_file(move.to_square) > chess.square_file(move.from_square) else "q"
            board.push(move)
        except Exception:
            break
        ply += 1
        wn, wb, wr, wq = _pc(mask(N, W)), _pc(mask(B, W)), _pc(mask(R, W)), _pc(mask(Q, W))
        bn, bb, br, bq = _pc(mask(N, K)), _pc(mask(B, K)), _pc(mask(R, K)), _pc(mask(Q, K))
        mat.append(_pc(mask(P, W)) - _pc(mask(P, K)) + 3 * (wn - bn) + 3 * (wb - bb) + 5 * (wr - br) + 9 * (wq - bq))

        if ply == 30:
            pawns_w, pawns_b = mask(P, W), mask(P, K)
            if _pc((pawns_w | pawns_b) & _FILE_DE) <= 2:
                feats.add("open_center")
            elif _pc(((pawns_w & _FILE_CF) << 8) & (pawns_b & _FILE_CF)) >= 2:
                feats.add("closed_center")
        if 30 <= ply <= 40 and ply % 2 == 0 and "isolated_queen_pawn" not in feats:
            mine = mask(P, me)
            if mine & chess.BB_FILE_D and not mine & (chess.BB_FILE_C | chess.BB_FILE_E):
                feats.add("isolated_queen_pawn")
        if ply == 50:
            if wq + bq == 0:
                feats.add("queenless")  # confirmed below once we know the game length
            my_b, foe_b = (wb, bb) if game.white else (bb, wb)
            if my_b >= 2 > foe_b:
                feats.add("bishop_pair_for")
            elif foe_b >= 2 > my_b:
                feats.add("bishop_pair_against")
        if endgame is None and ply >= 20:
            w_np, b_np = 3 * (wn + wb) + 5 * wr + 9 * wq, 3 * (bn + bb) + 5 * br + 9 * bq
            kind = None
            if w_np <= 13 and b_np <= 13:
                kind = ("queen_endgame" if wq + bq else "rook_endgame" if wr + br
                        else "minor_piece_endgame" if wn + wb + bn + bb else "pawn_endgame")
            if kind is not None and kind == endgame_prev:
                endgame = kind
            endgame_prev = kind
    if endgame is None:
        endgame = endgame_prev
    if endgame:
        feats.add(endgame)

    if "queenless" in feats and ply < 60:
        feats.discard("queenless")
    if len(castled) == 2:
        feats.add("opposite_castling" if castled[W] != castled[K] else "same_side_castling")

    game.features = feats
    game.replayed = bool(mat)
    if mat:
        sign = 1 if game.white else -1
        d = [sign * v for v in mat]
        low, high = _smooth(d)
        game.final_mat = d[-1]
        game.min_def = min(low)
        game.max_lead = max(high)
        game.tail_min = min(low[-10:])


# ── habits ────────────────────────────────────────────────────────────────────


def _local(end_time: int, tz_offset_minutes: int) -> datetime:
    return datetime.fromtimestamp(end_time + tz_offset_minutes * 60, tz=timezone.utc)


def _session_section(games: list[_Game]) -> tuple[dict[str, Any], dict[str, list[_Game]]]:
    ordered = sorted(games, key=lambda g: g.end_time)
    gap = SESSION_GAP_MINUTES * 60
    after: dict[str, list[tuple[float, float | None]]] = {"loss": [], "win": [], "draw": []}
    streak_items: list[tuple[float, float | None]] = []
    by_index: dict[str, list[tuple[float, float | None]]] = {k: [] for k, _ in SESSION_INDEX}
    sessions = 0
    idx = 0
    prev: _Game | None = None
    losses_in_row = 0
    for g in ordered:
        if prev is None or g.end_time - prev.end_time > gap:
            sessions += 1
            idx = 1
            prev_result = None
            losses_in_row = 0
        else:
            idx += 1
            prev_result = _result_word(prev.score)
            losses_in_row = losses_in_row + 1 if prev.score == 0 else 0
        if prev_result:
            after[prev_result].append(g.pair)
        if prev_result and losses_in_row >= 2:
            streak_items.append(g.pair)
        by_index["1" if idx == 1 else "2" if idx == 2 else "3" if idx == 3 else "4-5" if idx <= 5 else "6+"].append(g.pair)
        prev = g
    section = {
        "session_gap_minutes": SESSION_GAP_MINUTES,
        "sessions": sessions,
        "avg_games_per_session": round(len(ordered) / sessions, 1) if sessions else None,
        "after_loss": _split("after_loss", "Right after a loss", after["loss"]),
        "after_win": _split("after_win", "Right after a win", after["win"]),
        "after_draw": _split("after_draw", "Right after a draw", after["draw"]),
        "by_session_index": [_split(k, label, by_index[k]) for k, label in SESSION_INDEX],
        "on_losing_streak": _split("on_losing_streak", "After 2+ losses in a row", streak_items),
    }
    return section, {}


def _resignation_section(games: list[_Game]) -> dict[str, Any]:
    played = [g for g in games if g.replayed]
    resigned = [g for g in played if g.own_code == "resigned"]
    not_behind = [g for g in resigned if g.final_mat >= 0]
    mate_time = [g for g in played if g.own_code in ("checkmated", "timeout")]
    played_on = [g for g in mate_time if g.tail_min <= -5]
    was_down = [g for g in played if g.min_def <= -3]
    comebacks = [g for g in was_down if g.score >= 0.5]
    was_up = [g for g in played if g.max_lead >= 3]
    collapses = [g for g in was_up if g.score == 0]
    return {
        "resignations": len(resigned),
        "resigned_not_behind": len(not_behind),
        "resigned_not_behind_pct": _pct(len(not_behind), len(resigned)),
        "avg_material_at_resign": round(mean(g.final_mat for g in resigned), 1) if resigned else None,
        "played_on_lost": len(played_on),
        "played_on_lost_pct": _pct(len(played_on), len(mate_time)),
        "comebacks": len(comebacks),
        "comeback_rate_pct": _pct(len(comebacks), len(was_down)),
        "collapses_from_ahead": len(collapses),
        "collapse_rate_pct": _pct(len(collapses), len(was_up)),
        "_was_down": len(was_down),
        "_was_up": len(was_up),
        "_mate_time": len(mate_time),
    }


def _draw_section(games: list[_Game]) -> dict[str, Any]:
    draws = [g for g in games if g.score == 0.5]
    reasons = Counter(g.own_code or "other" for g in draws)
    return {
        "draws": len(draws),
        "draw_rate_pct": _pct(len(draws), len(games)),
        "by_reason": [{"reason": r, "games": c, "pct": _pct(c, len(draws))} for r, c in reasons.most_common()],
        "agreed_as_favourite": sum(
            1 for g in draws
            if g.own_code == "agreed" and g.own_rating is not None and g.foe_rating is not None and g.own_rating > g.foe_rating
        ),
    }


def _fmt_exp(split: dict[str, Any]) -> str:
    return f" (expected {split['expected_pct']:.0f}%)" if split["expected_pct"] is not None else ""


def _solid(split: dict[str, Any]) -> bool:
    return split["games"] >= MIN_SPLIT_GAMES and abs(split["shrunk_delta"]) >= MIN_ABS_SHRUNK


def _insights(games: list[_Game], sessions: dict, tod: list, weekday: list, positions: list, res: dict, draws: dict) -> list[str]:
    out: list[str] = []
    overall = _pct(sum(g.score for g in games), len(games))

    al = sessions["after_loss"]
    if _solid(al):
        if al["shrunk_delta"] < 0:
            out.append(f"Tilts: scores {al['score_pct']:.0f}% right after a loss (vs {overall:.0f}% overall)")
        else:
            out.append(f"Bounces back: scores {al['score_pct']:.0f}% right after a loss (vs {overall:.0f}% overall)")
    ls = sessions["on_losing_streak"]
    if _solid(ls) and ls["shrunk_delta"] < 0:
        out.append(f"Spirals on a losing streak: {ls['score_pct']:.0f}% after two or more losses in a row{_fmt_exp(ls)}")
    late = next((s for s in sessions["by_session_index"] if s["key"] == "6+"), None)
    if late and _solid(late) and late["shrunk_delta"] < 0:
        out.append(f"Fades in long sessions: {late['score_pct']:.0f}% from the 6th game of a session onward")

    for items, phrase in ((tod, lambda s: TOD_PHRASE[s["key"]]), (weekday, lambda s: f"on {s['label']}s")):
        solid = [s for s in items if _solid(s)]
        if solid:
            worst = min(solid, key=lambda s: s["shrunk_delta"])
            if worst["shrunk_delta"] < 0:
                out.append(f"Weakest {phrase(worst)}: {worst['score_pct']:.0f}%{_fmt_exp(worst)} over {worst['games']} games")

    solid_pos = [p for p in positions if _solid(p)]
    if solid_pos:
        worst = min(solid_pos, key=lambda p: p["shrunk_delta"])
        if worst["shrunk_delta"] < 0:
            out.append(f"Struggles in {worst['label'].lower()}: {worst['score_pct']:.0f}%{_fmt_exp(worst)}")
        best = max(solid_pos, key=lambda p: p["shrunk_delta"])
        if best["shrunk_delta"] > 0:
            out.append(f"Thrives in {best['label'].lower()}: {best['score_pct']:.0f}%{_fmt_exp(best)}")

    if res["resignations"] >= MIN_SPLIT_GAMES and res["resigned_not_behind_pct"] >= 30:
        out.append(f"Resigns early: {res['resigned_not_behind_pct']:.0f}% of resignations came with level material")
    if res["_mate_time"] >= MIN_SPLIT_GAMES and res["played_on_lost_pct"] >= 35:
        out.append(f"Plays on in lost positions: {res['played_on_lost_pct']:.0f}% of mate/time losses came after being 5+ points down")
    if res["_was_down"] >= MIN_SPLIT_GAMES and res["comeback_rate_pct"] >= 25:
        out.append(f"Fights on: won or drew {res['comeback_rate_pct']:.0f}% of games after being a piece down")
    if res["_was_up"] >= MIN_SPLIT_GAMES and res["collapse_rate_pct"] >= 25:
        out.append(f"Lets wins slip: lost {res['collapse_rate_pct']:.0f}% of games after being a piece up")
    if len(games) >= 20 and draws["draw_rate_pct"] >= 20:
        out.append(f"Draw-prone: {draws['draw_rate_pct']:.0f}% of games are drawn")
    if draws["agreed_as_favourite"] >= 3:
        out.append(f"Takes agreed draws as the higher-rated player ({draws['agreed_as_favourite']} times)")

    if games and len(out) < 3:
        out.append(f"{len(games)} games analysed across {sessions['sessions']} sessions; overall score {overall:.0f}%")
    return out[:7]


def build_habits(raw_games: list[dict], username: str, *, tz_offset_minutes: int = 0) -> dict:
    """Engine-free habit report for ``username`` (the ScoutHabits contract)."""
    games = [g for g in (_parse(raw, username) for raw in raw_games or []) if g is not None]
    # keep raw end_time for local-time bucketing (same order as ``games``)
    for g in games:
        if g.pgn:
            _replay(g)

    session_data, _ = _session_section(games)

    tod_items: dict[str, list] = {k: [] for k, _ in TOD_BUCKETS}
    wd_items: dict[str, list] = {k: [] for k, _ in WEEKDAYS}
    for g in games:
        if not g.end_time:
            continue
        local = _local(g.end_time, tz_offset_minutes)
        tod_items[TOD_BUCKETS[local.hour // 6][0]].append(g.pair)
        wd_items[WEEKDAYS[local.weekday()][0]].append(g.pair)
    time_of_day = [_split(k, label, tod_items[k]) for k, label in TOD_BUCKETS]
    weekday = [_split(k, label, wd_items[k]) for k, label in WEEKDAYS]

    replayed = [g for g in games if g.replayed]
    positions = []
    for key, (label, description) in POSITION_DEFS.items():
        having = [g for g in replayed if key in g.features]
        if not having:
            continue
        positions.append({
            **_split(key, label, [g.pair for g in having]),
            "description": description,
            "share": _pct(len(having), len(replayed)),
        })
    positions.sort(key=lambda p: -p["games"])

    resignation = _resignation_section(games)
    draws = _draw_section(games)
    insights = _insights(games, session_data, time_of_day, weekday, positions, resignation, draws)
    for k in [k for k in resignation if k.startswith("_")]:
        resignation.pop(k)
    return {
        "sessions": session_data,
        "time_of_day": time_of_day,
        "weekday": weekday,
        "positions": positions,
        "resignation": resignation,
        "draws": draws,
        "insights": insights,
    }


# ── head to head ──────────────────────────────────────────────────────────────


def build_head_to_head(raw_games: list[dict], username: str, me: str) -> dict | None:
    """Games between ``username`` and ``me`` from the scouted archive, from ME's POV.

    Returns None when they never played. Repeated lines group games by their
    first 8 plies; ``recent`` is the last 10 meetings.
    """
    user_l, me_l = username.casefold(), (me or "").casefold()
    if not me_l or user_l == me_l:
        return None
    rows = []
    for raw in raw_games or []:
        if raw.get("rules") not in (None, "chess"):
            continue
        w, b = (raw.get("white_username") or "").casefold(), (raw.get("black_username") or "").casefold()
        if {w, b} != {user_l, me_l}:
            continue
        me_white = w == me_l
        my_code = raw.get("white_result" if me_white else "black_result")
        score = _own_score(my_code)
        my_elo = their_elo = None
        sans: list[str] = []
        opening = "Unknown"
        try:
            game = chess.pgn.read_game(io.StringIO(raw.get("pgn") or ""))
        except Exception:
            game = None
        if game is not None:
            h = game.headers
            my_elo = _int(h.get("WhiteElo" if me_white else "BlackElo"))
            their_elo = _int(h.get("BlackElo" if me_white else "WhiteElo"))
            name = opening_from_eco_url(h.get("ECOUrl")) or h.get("Opening")
            if name and name != "?":
                opening = split_opening(name)[0] or "Unknown"
            board = game.board()
            for move in game.mainline_moves():
                if len(sans) >= H2H_LINE_PLIES:
                    break
                try:
                    sans.append(board.san(move))
                    board.push(move)
                except Exception:
                    break
        acc_me = raw.get("white_accuracy" if me_white else "black_accuracy")
        acc_them = raw.get("black_accuracy" if me_white else "white_accuracy")
        rows.append({
            "white": me_white, "score": score, "pair": (score, expected_score(my_elo, their_elo)),
            "sans": sans, "opening": opening, "end_time": int(raw.get("end_time") or 0),
            "date": raw.get("date"), "url": raw.get("url"), "time_class": raw.get("time_class"),
            "acc_me": acc_me, "acc_them": acc_them,
        })
    if not rows:
        return None
    rows.sort(key=lambda r: r["end_time"])
    n = len(rows)
    wins = sum(1 for r in rows if r["score"] == 1)
    draws = sum(1 for r in rows if r["score"] == 0.5)
    losses = n - wins - draws
    score_pct = _pct(sum(r["score"] for r in rows), n)

    def avg_acc(key: str) -> float | None:
        vals = []
        for r in rows:
            try:
                if r[key] is not None:
                    vals.append(float(r[key]))
            except (TypeError, ValueError):
                pass
        return round(mean(vals), 1) if vals else None

    you_white = _split("you_white", "You as White", [r["pair"] for r in rows if r["white"]])
    you_black = _split("you_black", "You as Black", [r["pair"] for r in rows if not r["white"]])

    groups: dict[tuple[str, tuple[str, ...]], list[dict]] = {}
    for r in rows:
        if r["sans"]:
            groups.setdefault(("white" if r["white"] else "black", tuple(r["sans"])), []).append(r)
    repeated = sorted(
        ((path, rs) for path, rs in groups.items() if len(rs) >= 2),
        key=lambda item: (-len(item[1]), item[0]),
    )[:5]
    repeated_lines = [
        {"path": list(path), "line": _line_text(list(path)), "you_color": you_color, "games": len(rs),
         "your_score_pct": _pct(sum(r["score"] for r in rs), len(rs))}
        for (you_color, path), rs in repeated
    ]

    recent = [
        {"date": r["date"], "url": r["url"], "you_color": "white" if r["white"] else "black",
         "result": _result_word(r["score"]), "opening": r["opening"], "time_class": r["time_class"]}
        for r in sorted(rows, key=lambda r: -r["end_time"])[:10]
    ]

    insights = [f"You are {wins}-{draws}-{losses} (W-D-L) against them: {score_pct:.0f}% over {n} game{'s' if n != 1 else ''}"]
    if you_white["games"] >= 2 and you_black["games"] >= 2 and abs(you_white["score_pct"] - you_black["score_pct"]) >= 20:
        better, worse = (("White", you_white), ("Black", you_black)) if you_white["score_pct"] > you_black["score_pct"] else (("Black", you_black), ("White", you_white))
        insights.append(f"You do better with {better[0]} ({better[1]['score_pct']:.0f}%) than with {worse[0]} ({worse[1]['score_pct']:.0f}%) against them")
    if repeated_lines:
        top = repeated_lines[0]
        insights.append(f"You keep reaching {top['line']} ({top['games']} games), scoring {top['your_score_pct']:.0f}%")
    mine, theirs = avg_acc("acc_me"), avg_acc("acc_them")
    if mine is not None and theirs is not None:
        insights.append(f"Average accuracy in these games: you {mine:.0f}%, them {theirs:.0f}%")
    last = recent[0]
    if len(insights) < 2 or (n >= 3 and all(r["result"] == last["result"] for r in recent[:3])):
        if n >= 3 and all(r["result"] == last["result"] for r in recent[:3]):
            insights.append(f"Your last 3 meetings were all {last['result']}s" if last["result"] != "loss" else "You have lost your last 3 meetings")
        else:
            insights.append(f"Most recent meeting: a {last['result']} as {last['you_color'].capitalize()}")
    return {
        "me": me,
        "games": n,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "score_pct": score_pct,
        "your_avg_accuracy": mine,
        "their_avg_accuracy": theirs,
        "you_white": you_white,
        "you_black": you_black,
        "repeated_lines": repeated_lines,
        "recent": recent,
        "insights": insights[:4],
    }
