"""Opponent "mistake fingerprint": how, when and where the scouted player goes wrong.

``build_fingerprint`` replays the scouted player's recent standard games, asks an
injected ``evaluate(board)`` callback (Stockfish in production, a fake in tests)
for one evaluation per position, and grades only *their* moves.

Conventions
-----------
* ``evaluate`` returns ``(eval_cp_side_to_move | None, best_move_san | None, pv_san)``
  with mate = +/-100000. Raw mate scores are kept for mate detection; every other
  calculation clips to +/-10000 first.
* With E_i the eval of position i from the side-to-move POV, the cp loss of the
  move p_i -> p_{i+1} is ``max(0, E_i + E_{i+1})``; a single loss is capped at 1000.
* mistake: loss >= 100 (and < 250); blunder: loss >= 250. ``phases[].mistakes``
  excludes blunders. Motif ``pct`` is the share of mistakes + blunders.
* Positions where the game is over are not sent to the engine: checkmate is
  -100000 for the side to move, any other terminal position 0.
* Evals are cached by EPD (FEN without move counters) within a run, so
  transpositions and repeated positions cost nothing.

Phases: opening = their moves 1-12; after that, endgame when the non-pawn
material of both sides together (Q9 R5 B3 N3) is <= 26, or <= 30 with queens off;
otherwise middlegame.

Motif heuristics (checked in this order, first match wins; only for mistakes and
blunders; "opponent reply" = the engine's best reply after their move)
* missed_mate   - their eval before the move was a forced mate, and after it isn't.
* allowed_mate  - after their move the opponent has a forced mate.
* hanging_piece - a piece worth >= 3 of theirs is attacked and either undefended
  or attacked by a cheaper piece, and the opponent's best reply captures on it.
* fork          - the reply's piece attacks 2+ of their pieces worth >= 3 (king
  counts) that are undefended or worth more than the attacker (king always).
* pin           - after the reply, a piece worth >= 3 of theirs is absolutely
  pinned, or is pinned to a more valuable queen/rook behind it.
* back_rank     - the opponent's best line has a rook/queen check on their back
  rank, with the king on that rank, shielded by its own pawns and unable to move.
* missed_capture- the engine's best move was a capture winning material (victim
  >= 3 and undefended or worth more than the capturer) and they didn't capture.
* king_safety   - the reply gives check or attacks a square next to their king.
* other.
Limitations: motifs are cheap one-ply geometric tests, not search. Pins/forks
that already existed before the move can still be credited to it, SEE is
ignored, and a mate score carries no distance, so any forced mate is "a mate".

Time pressure: ``clock_pct`` is the share of the base clock still on their clock
after they moved (``[%clk]`` of that move). Daily games and moves without a clock
are skipped.
"""

from __future__ import annotations

import io
import logging
from collections import defaultdict
from statistics import mean
from typing import Any, Callable

import chess
import chess.pgn

from .accuracy import move_accuracy
from .opponent_scout import _result_reason, opening_from_eco_url, parse_time_control, split_opening

logger = logging.getLogger(__name__)

MATE_RAW = 100000
MATE_CLIP = 10000
MATE_THRESHOLD = 90000          # |raw| above this is "forced mate"
MISTAKE_CP = 100
BLUNDER_CP = 250
LOSS_CAP = 1000
MIN_PLIES = 20
OPENING_LAST_MOVE = 12
CLIFF_MAX_MOVE = 20
WIN_EVAL = 200
CONVERSION_FROM_PLY = 20        # positions after move 10

PIECE_VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
PHASE_VALUE = {chess.QUEEN: 9, chess.ROOK: 5, chess.BISHOP: 3, chess.KNIGHT: 3}

MOTIF_LABELS = {
    "missed_mate": "Missed a forced mate",
    "allowed_mate": "Allowed a forced mate",
    "hanging_piece": "Left a piece hanging",
    "fork": "Walked into a fork",
    "pin": "Walked into a pin",
    "back_rank": "Back-rank weakness",
    "missed_capture": "Missed a winning capture",
    "king_safety": "Weakened king safety",
    "other": "Other mistakes",
}
MOTIF_INSIGHT = {
    "missed_mate": "Misses forced mates",
    "allowed_mate": "Allows forced mates",
    "hanging_piece": "Leaves pieces hanging",
    "fork": "Walks into forks",
    "pin": "Gets caught in pins",
    "back_rank": "Is exposed on the back rank",
    "missed_capture": "Misses winning captures",
    "king_safety": "Loses track of their king's safety",
}
BUCKETS = [
    ("plenty", "Plenty of time (over 50% left)"),
    ("comfortable", "Comfortable (20-50% left)"),
    ("low", "Low on time (10-20% left)"),
    ("scramble", "Scramble (under 10% left)"),
]

EvalResult = tuple["int | None", "str | None", "list[str]"]


# ── helpers ───────────────────────────────────────────────────────────────────


def _clip(value: int | float) -> int:
    return int(max(-MATE_CLIP, min(MATE_CLIP, value)))


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def _bucket_key(left_pct: float) -> str:
    if left_pct > 50:
        return "plenty"
    if left_pct >= 20:
        return "comfortable"
    if left_pct >= 10:
        return "low"
    return "scramble"


def _phase(board: chess.Board, move_number: int) -> str:
    if move_number <= OPENING_LAST_MOVE:
        return "opening"
    total = 0
    queens = 0
    for piece in board.piece_map().values():
        total += PHASE_VALUE.get(piece.piece_type, 0)
        if piece.piece_type == chess.QUEEN:
            queens += 1
    if total <= 26 or (queens == 0 and total <= 30):
        return "endgame"
    return "middlegame"


def _terminal_eval(board: chess.Board) -> EvalResult:
    return (-MATE_RAW if board.is_checkmate() else 0), None, []


def _try_san(board: chess.Board, san: str | None) -> chess.Move | None:
    if not san:
        return None
    try:
        return board.parse_san(san)
    except Exception:
        return None


# ── motif classification ──────────────────────────────────────────────────────


def _is_hanging(after: chess.Board, me: bool, reply: chess.Move | None) -> bool:
    if reply is None or not after.is_capture(reply) or after.is_en_passant(reply):
        return False
    sq = reply.to_square
    piece = after.piece_at(sq)
    if piece is None or piece.color != me or piece.piece_type == chess.KING or PIECE_VALUE[piece.piece_type] < 3:
        return False
    undefended = not after.is_attacked_by(me, sq)
    cheaper = any(PIECE_VALUE[after.piece_type_at(a)] < PIECE_VALUE[piece.piece_type] for a in after.attackers(not me, sq))
    return undefended or cheaper


def _is_fork(board_r: chess.Board, me: bool, reply: chess.Move | None) -> bool:
    if reply is None:
        return False
    attacker = board_r.piece_at(reply.to_square)
    if attacker is None:
        return False
    count = 0
    for tsq in chess.SquareSet(board_r.attacks_mask(reply.to_square) & board_r.occupied_co[me]):
        target = board_r.piece_at(tsq)
        if target is None:
            continue
        if target.piece_type == chess.KING:
            count += 1
        elif PIECE_VALUE[target.piece_type] >= 3 and (
            not board_r.is_attacked_by(me, tsq) or PIECE_VALUE[target.piece_type] > PIECE_VALUE[attacker.piece_type]
        ):
            count += 1
    return count >= 2


def _is_pin(board_r: chess.Board, me: bool) -> bool:
    opp = not me
    mine = [(sq, p) for sq, p in board_r.piece_map().items() if p.color == me and p.piece_type != chess.KING]
    for sq, piece in mine:
        if PIECE_VALUE[piece.piece_type] >= 3 and board_r.is_pinned(me, sq):
            return True
    heavy = [sq for sq, p in mine if p.piece_type in (chess.ROOK, chess.QUEEN)]
    for slider_sq in board_r.pieces(chess.BISHOP, opp) | board_r.pieces(chess.ROOK, opp) | board_r.pieces(chess.QUEEN, opp):
        for target in heavy:
            between = chess.SquareSet(chess.between(slider_sq, target)) & board_r.occupied
            if len(between) != 1:
                continue
            x = next(iter(between))
            px = board_r.piece_at(x)
            if px is None or px.color != me or PIECE_VALUE[px.piece_type] < 3:
                continue
            if PIECE_VALUE[px.piece_type] >= PIECE_VALUE[board_r.piece_at(target).piece_type]:  # type: ignore[union-attr]
                continue
            tmp = board_r.copy(stack=False)
            tmp.remove_piece_at(x)
            if target in tmp.attacks(slider_sq):
                return True
    return False


def _is_back_rank(after: chess.Board, me: bool, pv: list[str]) -> bool:
    ksq = after.king(me)
    back = 0 if me == chess.WHITE else 7
    if ksq is None or chess.square_rank(ksq) != back:
        return False
    tmp = after.copy(stack=False)
    for san in pv[:5]:
        move = _try_san(tmp, san)
        if move is None:
            return False
        mover = tmp.turn
        tmp.push(move)
        if mover == me or not tmp.is_check():
            continue
        piece = tmp.piece_at(move.to_square)
        if piece is None or piece.piece_type not in (chess.ROOK, chess.QUEEN) or chess.square_rank(move.to_square) != back:
            continue
        forward = back + (1 if me == chess.WHITE else -1)
        shield = [s for s in chess.SquareSet(chess.BB_KING_ATTACKS[ksq]) if chess.square_rank(s) == forward]
        if not shield or not all(tmp.piece_at(s) is not None and tmp.piece_at(s).color == me for s in shield):  # type: ignore[union-attr]
            continue
        if not any(tmp.piece_at(s).piece_type == chess.PAWN for s in shield):  # type: ignore[union-attr]
            continue
        if not any(m.from_square == ksq for m in tmp.legal_moves):
            return True
    return False


def _is_missed_capture(before: chess.Board, move: chess.Move, best_san: str | None) -> bool:
    best = _try_san(before, best_san)
    if best is None or not before.is_capture(best) or before.is_capture(move):
        return False
    mover = before.piece_type_at(best.from_square)
    if before.is_en_passant(best):
        return False  # a pawn for a pawn: never "winning" by this definition
    victim = before.piece_type_at(best.to_square)
    if mover is None or victim is None or PIECE_VALUE[victim] < 3:
        return False
    return PIECE_VALUE[victim] > PIECE_VALUE[mover] or not before.is_attacked_by(not before.turn, best.to_square)


def classify_motif(
    before: chess.Board,
    move: chess.Move,
    e_before: int,
    e_after: int,
    best_san: str | None,
    reply_san: str | None,
    reply_pv: list[str],
) -> str:
    """Motif of a mistake. ``e_before``/``e_after`` are raw evals (mover / opponent POV)."""
    me = before.turn
    if e_before >= MATE_THRESHOLD and -e_after < MATE_THRESHOLD:
        return "missed_mate"
    if e_after >= MATE_THRESHOLD:
        return "allowed_mate"
    after = before.copy(stack=False)
    after.push(move)
    reply = _try_san(after, reply_san)
    board_r = after
    if reply is not None:
        board_r = after.copy(stack=False)
        board_r.push(reply)
    if _is_hanging(after, me, reply):
        return "hanging_piece"
    if _is_fork(board_r, me, reply):
        return "fork"
    if _is_pin(board_r, me):
        return "pin"
    if _is_back_rank(after, me, reply_pv):
        return "back_rank"
    if _is_missed_capture(before, move, best_san):
        return "missed_capture"
    ksq = after.king(me)
    if reply is not None and ksq is not None:
        if after.gives_check(reply) or (board_r.attacks_mask(reply.to_square) & chess.BB_KING_ATTACKS[ksq]):
            return "king_safety"
    return "other"


# ── game preparation ──────────────────────────────────────────────────────────


class _Game:
    def __init__(self) -> None:
        self.white = True
        self.moves: list[chess.Move] = []
        self.clocks: list[float | None] = []
        self.base: float | None = None
        self.family = "Unknown"
        self.url: str | None = None
        self.score = 0.0
        self.boards: list[chess.Board] = []     # positions p0..pN


def _prepare(raw: dict, username: str, max_plies: int) -> _Game | None:
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
        pgn = chess.pgn.read_game(io.StringIO(raw.get("pgn") or ""))
    except Exception:
        return None
    if pgn is None:
        return None
    board = pgn.board()
    if board.fen() != chess.STARTING_FEN:
        return None

    g = _Game()
    g.white = white
    g.boards.append(board.copy(stack=False))
    total = 0
    for node in pgn.mainline():
        total += 1
        if total > max_plies:
            continue  # keep counting plies for the length filter
        try:
            board.push(node.move)
        except Exception:
            break
        g.moves.append(node.move)
        g.clocks.append(node.clock())
        g.boards.append(board.copy(stack=False))
    if total < MIN_PLIES or len(g.moves) < 2:
        return None

    base, _inc = parse_time_control(raw.get("time_control") or pgn.headers.get("TimeControl"))
    g.base = base
    name = opening_from_eco_url(pgn.headers.get("ECOUrl"))
    if name:
        g.family = split_opening(name)[0] or "Unknown"
    elif pgn.headers.get("Opening"):
        g.family = split_opening(pgn.headers["Opening"])[0]
    g.url = raw.get("url")
    own_code = raw.get("white_result" if white else "black_result")
    foe_code = raw.get("black_result" if white else "white_result")
    g.score = _result_reason(own_code, foe_code)[0]
    return g


# ── main entry ────────────────────────────────────────────────────────────────


def build_fingerprint(
    raw_games: list[dict],
    username: str,
    evaluate: Callable[[chess.Board], tuple[int | None, str | None, list[str]]],
    *,
    depth: int,
    max_games: int = 40,
    max_plies: int = 120,
    progress: Callable[[int, int], None] | None = None,
) -> dict | None:
    ordered = sorted(raw_games, key=lambda r: -(r.get("end_time") or 0))
    games: list[_Game] = []
    for raw in ordered:
        if len(games) >= max_games:
            break
        g = _prepare(raw, username, max_plies)
        if g is not None:
            games.append(g)
    if not games:
        return None

    total_positions = sum(len(g.boards) for g in games)
    done = 0
    cache: dict[str, EvalResult] = {}

    def ev(board: chess.Board) -> EvalResult:
        key = board.epd()
        hit = cache.get(key)
        if hit is None:
            hit = _terminal_eval(board) if board.is_game_over() else evaluate(board)
            cache[key] = hit
        return hit

    moves_rec: list[dict[str, Any]] = []
    conv = {"winning": 0, "converted": 0, "losing": 0, "saved": 0}
    cliff_data: dict[tuple[str, str], dict[int, dict[int, float]]] = defaultdict(dict)  # key -> game idx -> move -> loss
    cliff_games: dict[tuple[str, str], int] = defaultdict(int)

    for gi, g in enumerate(games):
        evals: list[EvalResult] = []
        for board in g.boards:
            evals.append(ev(board))
            done += 1
            if progress is not None:
                try:
                    progress(done, total_positions)
                except Exception:
                    logger.debug("fingerprint progress callback failed", exc_info=True)

        me = chess.WHITE if g.white else chess.BLACK
        color = "white" if g.white else "black"
        key = (g.family, color)
        cliff_games[key] += 1
        per_move: dict[int, float] = {}

        for i, move in enumerate(g.moves):
            if (i % 2 == 0) != g.white:
                continue
            e0, e1 = evals[i][0], evals[i + 1][0]
            if e0 is None or e1 is None:
                continue
            loss = min(LOSS_CAP, max(0, _clip(e0) + _clip(e1)))
            number = i // 2 + 1
            acc = move_accuracy(_clip(e0), _clip(e1))
            clock_left = None
            clk = g.clocks[i]
            if g.base and clk is not None:
                clock_left = max(0.0, clk / g.base * 100)
            before = g.boards[i]
            rec: dict[str, Any] = {
                "loss": loss, "number": number, "phase": _phase(before, number), "acc": acc,
                "clock_left": clock_left, "color": color, "family": g.family, "url": g.url,
            }
            if loss >= MISTAKE_CP:
                reply = evals[i + 1]
                rec["motif"] = classify_motif(before, move, e0, e1, evals[i][1], reply[1], reply[2])
                rec["fen"] = before.fen()
                rec["played"] = before.san(move)
                rec["best"] = evals[i][1] or ""
            moves_rec.append(rec)
            if number <= CLIFF_MAX_MOVE:
                per_move[number] = float(loss)
        if per_move:
            cliff_data[key][gi] = per_move

        # conversion: their-POV eval at any position after move 10
        pov = []
        for j in range(CONVERSION_FROM_PLY, len(g.boards)):
            e = evals[j][0]
            if e is not None:
                pov.append(_clip(e) if g.boards[j].turn == me else -_clip(e))
        if pov and max(pov) >= WIN_EVAL:
            conv["winning"] += 1
            conv["converted"] += g.score == 1.0
        if pov and min(pov) <= -WIN_EVAL:
            conv["losing"] += 1
            conv["saved"] += g.score >= 0.5

    if not moves_rec:
        return {
            "games_analyzed": len(games), "moves_analyzed": 0, "depth": depth, "avg_cp_loss": None,
            "accuracy_estimate": None, "phases": [], "opening_cliffs": [], "motifs": [],
            "time_pressure": {"buckets": [{"key": k, "label": lbl, "moves": 0, "avg_cp_loss": None, "blunder_rate": 0.0} for k, lbl in BUCKETS]},
            "conversion": {"winning_games": 0, "converted": 0, "converted_pct": 0.0, "losing_games": 0, "saved": 0, "saved_pct": 0.0},
            "worst_mistakes": [], "insights": [],
        }

    n = len(moves_rec)
    avg_loss = mean(r["loss"] for r in moves_rec)
    accs = [r["acc"] for r in moves_rec if r["acc"] is not None]

    # phases
    phases = []
    for name in ("opening", "middlegame", "endgame"):
        rows = [r for r in moves_rec if r["phase"] == name]
        blunders = sum(1 for r in rows if r["loss"] >= BLUNDER_CP)
        phases.append({
            "phase": name,
            "moves": len(rows),
            "avg_cp_loss": round(mean(r["loss"] for r in rows), 1) if rows else None,
            "mistakes": sum(1 for r in rows if MISTAKE_CP <= r["loss"] < BLUNDER_CP),
            "blunders": blunders,
            "blunder_rate": _pct(blunders, len(rows)),
        })

    # opening cliffs
    cliffs = []
    for (family, color), by_game in cliff_data.items():
        if cliff_games[(family, color)] < 3:
            continue
        by_move = []
        for m in range(1, CLIFF_MAX_MOVE + 1):
            vals = [pm[m] for pm in by_game.values() if m in pm]
            if len(vals) >= 2:
                by_move.append({"move": m, "avg_cp_loss": round(mean(vals), 1), "samples": len(vals)})
        means = {row["move"]: row["avg_cp_loss"] for row in by_move}
        cliff = None
        for m in range(4, CLIFF_MAX_MOVE - 1):
            if not all(x in means for x in (m, m + 1, m + 2)):
                continue
            prior = [means[x] for x in range(1, m) if x in means]
            if not prior:
                continue
            window = mean(means[x] for x in (m, m + 1, m + 2))
            if window >= 40 and window >= 2 * mean(prior):
                cliff = m
                break
        before_vals = [v for k, v in means.items() if cliff is not None and k < cliff]
        after_vals = [v for k, v in means.items() if cliff is not None and k >= cliff]
        cliffs.append({
            "family": family,
            "color": color,
            "games": cliff_games[(family, color)],
            "cliff_move": cliff,
            "avg_cp_loss_before": round(mean(before_vals), 1) if before_vals else None,
            "avg_cp_loss_after": round(mean(after_vals), 1) if after_vals else None,
            "by_move": by_move,
        })
    cliffs.sort(key=lambda c: (-c["games"], c["family"], c["color"]))

    # mistakes / motifs
    def example(r: dict[str, Any]) -> dict[str, Any]:
        return {
            "fen": r["fen"], "played": r["played"], "best": r["best"], "cp_loss": int(r["loss"]),
            "move_number": r["number"], "color": r["color"], "motif": r["motif"], "family": r["family"],
            "url": r["url"], "clock_pct": round(r["clock_left"], 1) if r["clock_left"] is not None else None,
        }

    bad = [r for r in moves_rec if "motif" in r]
    motifs = []
    for motif in MOTIF_LABELS:
        rows = [r for r in bad if r["motif"] == motif]
        if rows:
            worst = max(rows, key=lambda r: r["loss"])
            motifs.append({"motif": motif, "label": MOTIF_LABELS[motif], "count": len(rows),
                           "pct": _pct(len(rows), len(bad)), "example": example(worst)})
    motifs.sort(key=lambda m: -m["count"])
    worst_mistakes = [example(r) for r in sorted(bad, key=lambda r: -r["loss"])[:8]]

    # time pressure
    buckets = []
    for key, label in BUCKETS:
        rows = [r for r in moves_rec if r["clock_left"] is not None and _bucket_key(r["clock_left"]) == key]
        blunders = sum(1 for r in rows if r["loss"] >= BLUNDER_CP)
        buckets.append({
            "key": key, "label": label, "moves": len(rows),
            "avg_cp_loss": round(mean(r["loss"] for r in rows), 1) if rows else None,
            "blunder_rate": _pct(blunders, len(rows)),
        })

    conversion = {
        "winning_games": conv["winning"], "converted": conv["converted"],
        "converted_pct": _pct(conv["converted"], conv["winning"]),
        "losing_games": conv["losing"], "saved": conv["saved"],
        "saved_pct": _pct(conv["saved"], conv["losing"]),
    }

    insights = _insights(phases, cliffs, motifs, buckets, conversion, moves_rec, len(bad))

    return {
        "games_analyzed": len(games),
        "moves_analyzed": n,
        "depth": depth,
        "avg_cp_loss": round(avg_loss, 1),
        "accuracy_estimate": round(mean(accs), 1) if accs else None,
        "phases": phases,
        "opening_cliffs": cliffs,
        "motifs": motifs,
        "time_pressure": {"buckets": buckets},
        "conversion": conversion,
        "worst_mistakes": worst_mistakes,
        "insights": insights,
    }


def _insights(phases, cliffs, motifs, buckets, conversion, moves_rec, bad_count) -> list[str]:
    out: list[str] = []

    # time pressure
    scramble = next(b for b in buckets if b["key"] == "scramble")
    calm = [r for r in moves_rec if r["clock_left"] is not None and r["clock_left"] >= 20]
    if scramble["moves"] >= 20 and len(calm) >= 40:
        calm_rate = sum(1 for r in calm if r["loss"] >= BLUNDER_CP) / len(calm) * 100
        s_blunders = round(scramble["blunder_rate"] * scramble["moves"] / 100)
        if calm_rate > 0 and scramble["blunder_rate"] >= 2 * calm_rate:
            out.append(f"Blunders {scramble['blunder_rate'] / calm_rate:.0f}x more often with under 10% of their clock")
        elif calm_rate == 0 and s_blunders >= 3:
            out.append("Blunders almost only when under 10% of their clock is left")

    # opening cliffs
    for c in cliffs:
        if c["games"] >= 3 and c["cliff_move"] is not None:
            out.append(f"In the {c['family']} as {c['color'].capitalize()} their play drops off after move {c['cliff_move'] - 1}")
            break

    # dominant motif
    for m in motifs:
        if m["motif"] != "other" and m["count"] >= 4 and m["pct"] >= 25 and bad_count >= 8:
            out.append(f"{MOTIF_INSIGHT[m['motif']]} more than anything else ({m['pct']:.0f}% of their mistakes)")
            break

    # weakest phase
    rated = [p for p in phases if p["moves"] >= 60]
    if len(rated) >= 2:
        worst = max(rated, key=lambda p: p["blunder_rate"])
        others = [p["blunder_rate"] for p in rated if p is not worst]
        if worst["blunder_rate"] >= 1 and worst["blunder_rate"] >= 1.5 * max(others):
            out.append(f"Most of their blunders come in the {worst['phase']} ({worst['blunder_rate']:.1f} per 100 moves)")

    # conversion
    if conversion["winning_games"] >= 5 and conversion["converted_pct"] <= 65:
        out.append(f"Converts only {conversion['converted_pct']:.0f}% of winning positions")
    if conversion["losing_games"] >= 5 and conversion["saved_pct"] >= 30:
        out.append(f"Saves {conversion['saved_pct']:.0f}% of positions where they were clearly worse")
    return out[:6]
