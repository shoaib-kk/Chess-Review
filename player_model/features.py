"""Player feature extraction (Phase 2).

Reads the raw position data produced by Phase 1 and computes a structured,
statistical player profile. **No new Stockfish calls** happen here — every
feature is derived from stored data or from cheap python-chess computation on the
stored FENs.

Design notes
------------
* Each feature group is a pure function taking the player's positions (and, where
  relevant, games). They accept anything with the right attributes — SQLAlchemy
  ``Position``/``Game`` rows or the lightweight stand-ins used by the unit tests.
* Graceful degradation: features that need a statistically meaningful sample
  return ``None`` when fewer than ``MIN_SAMPLES`` data points are available.
  Occurrence ratios return ``None`` when their denominator is zero.
* Determinism: ordering, sampling (every 5th position) and ``statistics`` are all
  deterministic given the same input rows.
"""

from __future__ import annotations

import io
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

import chess
import chess.pgn

from . import config
from .analyzer import _is_sacrifice  # reuse Phase 1's sacrifice heuristic

# Minimum sample size before a statistical feature is considered meaningful.
MIN_SAMPLES = 10

# Material values in pawns (kings excluded from material totals).
_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}
_TRADE_PIECE_TYPES = {
    "Q": chess.QUEEN,
    "R": chess.ROOK,
    "B": chess.BISHOP,
    "N": chess.KNIGHT,
}

# An endgame is reached once total material on the board drops below this (pawns).
ENDGAME_MATERIAL = 20
# Material edge (pawns) that counts as "entering an endgame ahead".
ENDGAME_EDGE = 1.5
# Time-pressure threshold in seconds.
TIME_PRESSURE_SECONDS = 30


# --------------------------------------------------------------------------- #
# Small shared helpers
# --------------------------------------------------------------------------- #
def _board(fen: str) -> Optional[chess.Board]:
    try:
        return chess.Board(fen)
    except (ValueError, KeyError):
        return None


def _move(uci: Optional[str]) -> Optional[chess.Move]:
    if not uci:
        return None
    try:
        return chess.Move.from_uci(uci)
    except (chess.InvalidMoveError, ValueError):
        return None


def _mean(values: Sequence[float]) -> Optional[float]:
    return round(statistics.fmean(values), 4) if values else None


def _accuracy_from_cpl(mean_cpl: float) -> float:
    """Chess.com accuracy formula."""
    return round(103.1668 * math.exp(-0.04354 * mean_cpl) - 3.1669, 4)


def _is_inaccuracy(p) -> bool:
    """Inaccuracy = >50cp lost but not already a mistake/blunder."""
    return (
        p.cpl is not None
        and p.cpl > config.INACCURACY_CPL
        and not p.is_mistake
        and not p.is_blunder
    )


def _material(board: chess.Board, color: chess.Color) -> int:
    return sum(
        _PIECE_VALUES[pt] * len(board.pieces(pt, color)) for pt in _PIECE_VALUES
    )


def _total_material(board: chess.Board) -> int:
    return _material(board, chess.WHITE) + _material(board, chess.BLACK)


def _won_game(game) -> Optional[bool]:
    """True if the target player won, False if drew/lost, None if undeterminable."""
    result = getattr(game, "result", None)
    color = getattr(game, "color_played", None)
    if not result or color not in ("white", "black"):
        return None
    if result == "1-0":
        return color == "white"
    if result == "0-1":
        return color == "black"
    return False  # draw or unknown


# --------------------------------------------------------------------------- #
# 1. Accuracy features
# --------------------------------------------------------------------------- #
def accuracy_features(positions: Sequence, games: Sequence) -> dict:
    cpls = [p.cpl for p in positions if p.cpl is not None]
    n = len(cpls)
    if n < MIN_SAMPLES:
        return {
            "mean_cpl": None,
            "median_cpl": None,
            "cpl_std": None,
            "accuracy_score": None,
            "blunder_rate": None,
            "mistake_rate": None,
            "inaccuracy_rate": None,
            "accuracy_variance_across_games": None,
        }

    mean_cpl = statistics.fmean(cpls)
    blunders = sum(1 for p in positions if p.is_blunder)
    mistakes = sum(1 for p in positions if p.is_mistake)
    inaccuracies = sum(1 for p in positions if _is_inaccuracy(p))

    # Per-game accuracy spread (needs >= 2 games to have a variance).
    per_game_scores: list[float] = []
    by_game: dict[int, list[int]] = {}
    for p in positions:
        if p.cpl is not None:
            by_game.setdefault(p.game_id, []).append(p.cpl)
    for game_cpls in by_game.values():
        per_game_scores.append(_accuracy_from_cpl(statistics.fmean(game_cpls)))
    variance = (
        round(statistics.stdev(per_game_scores), 4)
        if len(per_game_scores) >= 2
        else None
    )

    return {
        "mean_cpl": round(mean_cpl, 4),
        "median_cpl": round(statistics.median(cpls), 4),
        "cpl_std": round(statistics.stdev(cpls), 4) if n >= 2 else 0.0,
        "accuracy_score": _accuracy_from_cpl(mean_cpl),
        "blunder_rate": round(blunders / n * 10, 4),
        "mistake_rate": round(mistakes / n * 10, 4),
        "inaccuracy_rate": round(inaccuracies / n * 10, 4),
        "accuracy_variance_across_games": variance,
    }


# --------------------------------------------------------------------------- #
# 2. Tactical features
# --------------------------------------------------------------------------- #
def tactical_features(positions: Sequence) -> dict:
    n = len(positions)
    brilliant_rate = (
        round(sum(1 for p in positions if p.is_brilliant) / n * 10, 4)
        if n >= MIN_SAMPLES
        else None
    )

    opportunities = found = 0
    sacrifices = 0
    complexity_counts: list[int] = []

    for p in positions:
        board = _board(p.fen)
        if board is None:
            continue
        best = _move(p.best_move)
        played = _move(p.move_played)

        # Tactical opportunity: the top move grabs material and the position is
        # clearly winning (>150cp from the mover's POV). Proxy for "eval jumps".
        if best is not None and p.eval_before is not None and p.eval_before > 150:
            if board.is_capture(best):
                opportunities += 1
                if played is not None and played == best:
                    found += 1

        # Voluntary material sacrifice that is not an outright blunder.
        if played is not None and not p.is_blunder and _is_sacrifice(board, played):
            sacrifices += 1

        # Complexity: how many of the stored top-N candidates are within 50cp of
        # the best one (more near-equal choices = a more complex position).
        if p.candidate_evals and len(p.candidate_evals) >= 2:
            best_eval = p.candidate_evals[0]
            within = sum(1 for e in p.candidate_evals if abs(best_eval - e) <= 50)
            complexity_counts.append(within)

    return {
        "brilliant_move_rate": brilliant_rate,
        "tactical_opportunity_conversion": (
            round(found / opportunities, 4) if opportunities else None
        ),
        "sacrifice_tendency": (
            round(sacrifices / n, 4) if n >= MIN_SAMPLES else None
        ),
        "complexity_preference": (
            round(statistics.fmean(complexity_counts), 4)
            if len(complexity_counts) >= MIN_SAMPLES
            else None
        ),
    }


# --------------------------------------------------------------------------- #
# 3. Positional features (python-chess from FEN; positions are player-to-move)
# --------------------------------------------------------------------------- #
def _pawn_structure(board: chess.Board, color: chess.Color) -> tuple[int, int, int]:
    pawns = list(board.pieces(chess.PAWN, color))
    files = [chess.square_file(sq) for sq in pawns]
    file_counts = Counter(files)

    doubled = sum(c - 1 for c in file_counts.values() if c > 1)
    isolated = sum(
        1 for f in files if (f - 1) not in file_counts and (f + 1) not in file_counts
    )

    enemy_pawns = board.pieces(chess.PAWN, not color)
    enemy_by_file: dict[int, list[int]] = {}
    for sq in enemy_pawns:
        enemy_by_file.setdefault(chess.square_file(sq), []).append(chess.square_rank(sq))

    passed = 0
    forward = 1 if color == chess.WHITE else -1
    for sq in pawns:
        f, r = chess.square_file(sq), chess.square_rank(sq)
        blocked = False
        for adj in (f - 1, f, f + 1):
            for er in enemy_by_file.get(adj, []):
                if (er - r) * forward > 0:  # an enemy pawn ahead on this file
                    blocked = True
                    break
            if blocked:
                break
        if not blocked:
            passed += 1
    return doubled, isolated, passed


def _king_safety(board: chess.Board, color: chess.Color) -> float:
    king_sq = board.king(color)
    if king_sq is None:
        return 0.0
    kf, kr = chess.square_file(king_sq), chess.square_rank(king_sq)
    home_rank = 0 if color == chess.WHITE else 7
    forward = 1 if color == chess.WHITE else -1

    score = 50.0
    if kf in (2, 6) and kr == home_rank:  # castled (queenside/kingside)
        score += 20.0

    shield_files = [f for f in (kf - 1, kf, kf + 1) if 0 <= f <= 7]
    shield = 0
    own_pawns = board.pieces(chess.PAWN, color)
    for f in shield_files:
        for dr in (1, 2):
            sq = chess.square(f, kr + forward * dr)
            if 0 <= kr + forward * dr <= 7 and sq in own_pawns:
                shield += 1
                break
    score += 5.0 * min(shield, 3)

    open_files = 0
    for f in shield_files:
        if not any(chess.square_file(sq) == f for sq in own_pawns):
            open_files += 1
    score -= 10.0 * open_files

    return max(0.0, min(100.0, score))


def positional_features(positions: Sequence) -> dict:
    if len(positions) < MIN_SAMPLES:
        return {
            "pawn_structure_score": None,
            "king_safety_index": None,
            "piece_activity_index": None,
        }

    doubled_t = isolated_t = passed_t = 0
    king_scores: list[float] = []
    pawn_n = 0
    for p in positions:
        board = _board(p.fen)
        if board is None:
            continue
        color = board.turn  # stored positions are always the player's move
        d, i, ps = _pawn_structure(board, color)
        doubled_t += d
        isolated_t += i
        passed_t += ps
        king_scores.append(_king_safety(board, color))
        pawn_n += 1

    # Mobility is the only potentially expensive part — sample every 5th position.
    mobilities: list[int] = []
    for p in positions[::5]:
        board = _board(p.fen)
        if board is not None:
            mobilities.append(board.legal_moves.count())

    return {
        "pawn_structure_score": {
            "doubled_pawns": round(doubled_t / pawn_n, 4),
            "isolated_pawns": round(isolated_t / pawn_n, 4),
            "passed_pawns": round(passed_t / pawn_n, 4),
        }
        if pawn_n
        else None,
        "king_safety_index": _mean(king_scores),
        "piece_activity_index": _mean(mobilities),
    }


# --------------------------------------------------------------------------- #
# 4. Endgame features
# --------------------------------------------------------------------------- #
def endgame_features(positions: Sequence, games: Sequence) -> dict:
    by_game: dict[int, list] = {}
    for p in positions:
        by_game.setdefault(p.game_id, []).append(p)

    games_by_id = {g.id: g for g in games}

    endgame_cpls: list[int] = []
    endgame_games = 0
    eligible = wins = 0

    for game_id, game_positions in by_game.items():
        ordered = sorted(game_positions, key=lambda x: x.ply)
        entered = False
        for p in ordered:
            board = _board(p.fen)
            if board is None:
                continue
            if _total_material(board) < ENDGAME_MATERIAL:
                if p.cpl is not None:
                    endgame_cpls.append(p.cpl)
                if not entered:
                    entered = True
                    endgame_games += 1
                    # Material edge at the moment of entering the endgame.
                    player = board.turn
                    edge = _material(board, player) - _material(board, not player)
                    game = games_by_id.get(game_id)
                    won = _won_game(game) if game is not None else None
                    if edge > ENDGAME_EDGE and won is not None:
                        eligible += 1
                        if won:
                            wins += 1

    return {
        "endgame_game_count": endgame_games,
        "endgame_accuracy": (
            round(statistics.fmean(endgame_cpls), 4)
            if len(endgame_cpls) >= MIN_SAMPLES
            else None
        ),
        "endgame_conversion_rate": round(wins / eligible, 4) if eligible else None,
    }


# --------------------------------------------------------------------------- #
# 5. Style features
# --------------------------------------------------------------------------- #
def _trade_info(board: chess.Board, played: Optional[chess.Move]):
    """Return (options, initiated) sets of piece-type labels for one position.

    A "trade option" for piece type T exists when the player can capture an enemy
    T that is defended (so a recapture is available — a genuine trade rather than
    winning a hanging piece). ``initiated`` is the subset the player's move took.
    """
    player = board.turn
    options: set[str] = set()
    initiated: set[str] = set()

    def captured_type(move: chess.Move) -> Optional[int]:
        if board.is_en_passant(move):
            return chess.PAWN
        piece = board.piece_at(move.to_square)
        return piece.piece_type if piece else None

    for move in board.legal_moves:
        if not board.is_capture(move):
            continue
        ctype = captured_type(move)
        if ctype is None:
            continue
        # Recapture available -> it's a trade, not a free win.
        defended = bool(board.attackers(not player, move.to_square))
        if not defended:
            continue
        for label, pt in _TRADE_PIECE_TYPES.items():
            if ctype == pt:
                options.add(label)
                if played is not None and move == played:
                    initiated.add(label)
    return options, initiated


def _creates_threat(board: chess.Board, move: chess.Move) -> bool:
    """Does the move leave an enemy piece attacked and undefended (a new threat)?"""
    player = board.turn
    after = board.copy(stack=False)
    after.push(move)
    for sq in chess.SQUARES:
        piece = after.piece_at(sq)
        if piece is None or piece.color == player:
            continue
        if after.attackers(player, sq) and not after.attackers(not player, sq):
            return True
    return False


def style_features(positions: Sequence) -> dict:
    n = len(positions)
    eval_magnitudes = [abs(p.eval_before) for p in positions if p.eval_before is not None]

    opt = Counter()
    init = Counter()
    initiative_hits = 0
    initiative_n = 0

    for p in positions:
        board = _board(p.fen)
        if board is None:
            continue
        played = _move(p.move_played)

        options, initiated = _trade_info(board, played)
        for label in options:
            opt[label] += 1
        for label in initiated:
            init[label] += 1

        if played is not None and played in board.legal_moves:
            initiative_n += 1
            if (
                board.gives_check(played)
                or board.is_capture(played)
                or _creates_threat(board, played)
            ):
                initiative_hits += 1

    trade_pref = {
        label: (round(init[label] / opt[label], 4) if opt[label] else None)
        for label in _TRADE_PIECE_TYPES
    }
    queen_avoidance = (
        round(1 - init["Q"] / opt["Q"], 4) if opt["Q"] else None
    )

    return {
        "aggression_index": (
            round(statistics.fmean(eval_magnitudes), 4)
            if len(eval_magnitudes) >= MIN_SAMPLES
            else None
        ),
        "trade_preference_by_piece": trade_pref,
        "queen_trade_avoidance": queen_avoidance,
        "initiative_index": (
            round(initiative_hits / initiative_n, 4)
            if initiative_n >= MIN_SAMPLES
            else None
        ),
    }


# --------------------------------------------------------------------------- #
# 6. Opening features
# --------------------------------------------------------------------------- #
def _eco_for_game(game) -> Optional[str]:
    """Pull the ECO code from the game's PGN header (optional opening fallback)."""
    pgn = getattr(game, "pgn_raw", None)
    if not pgn:
        return None
    try:
        parsed = chess.pgn.read_game(io.StringIO(pgn))
    except Exception:
        return None
    if parsed is None:
        return None
    eco = parsed.headers.get("ECO")
    if eco and eco not in ("?", "-", ""):
        return eco.strip()
    # Optional fallback to the repo's opening recogniser if it's importable
    # (it isn't bundled into the Phase 2 container, so this stays best-effort).
    try:
        from opening_recognition import recognise_opening  # type: ignore

        info = recognise_opening(parsed)
        if info and info.eco:
            return info.eco
    except Exception:
        pass
    return None


def opening_features(positions: Sequence, games: Sequence) -> dict:
    eco_counts = Counter()
    for g in games:
        eco = _eco_for_game(g)
        if eco:
            eco_counts[eco] += 1

    # Opening accuracy: first 15 full moves == first 30 plies.
    opening_cpls = [p.cpl for p in positions if p.ply <= 30 and p.cpl is not None]
    opening_accuracy = (
        round(statistics.fmean(opening_cpls), 4)
        if len(opening_cpls) >= MIN_SAMPLES
        else None
    )

    total = sum(eco_counts.values())
    if total == 0:
        flexibility = None
    else:
        flexibility = round(
            -sum((c / total) * math.log2(c / total) for c in eco_counts.values()), 4
        )

    return {
        "eco_distribution": dict(eco_counts),
        "opening_repertoire_size": len(eco_counts),
        "opening_accuracy": opening_accuracy,
        "opening_flexibility": flexibility,
    }


# --------------------------------------------------------------------------- #
# 7. Time features (null unless clock data is present)
# --------------------------------------------------------------------------- #
def time_features(positions: Sequence) -> dict:
    timed = [p for p in positions if getattr(p, "clock_seconds", None) is not None]
    if not timed:
        return {"time_pressure_cpl": None, "time_pressure_blunder_rate": None}

    low = [p for p in timed if p.clock_seconds < TIME_PRESSURE_SECONDS]
    cpls = [p.cpl for p in low if p.cpl is not None]

    return {
        "time_pressure_cpl": (
            round(statistics.fmean(cpls), 4) if len(cpls) >= MIN_SAMPLES else None
        ),
        "time_pressure_blunder_rate": (
            round(sum(1 for p in low if p.is_blunder) / len(low) * 10, 4)
            if len(low) >= MIN_SAMPLES
            else None
        ),
    }


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
def assemble_features(positions: Sequence, games: Sequence) -> dict:
    """Compute the full feature dict from in-memory rows (no DB access).

    Split out from :func:`compute_player_profile` so it can be unit-tested with
    hardcoded data and reused without a Session.
    """
    return {
        "accuracy": accuracy_features(positions, games),
        "tactical": tactical_features(positions),
        "positional": positional_features(positions),
        "endgame": endgame_features(positions, games),
        "style": style_features(positions),
        "opening": opening_features(positions, games),
        "time": time_features(positions),
    }


def compute_player_profile(player_id: int, db) -> dict:
    """Compute and upsert the structured profile for ``player_id``.

    Returns the assembled feature dict. Reads only Phase 1 data; performs no
    Stockfish calls.
    """
    from sqlalchemy import select

    from .models import Game, PlayerProfile, Position

    games = list(db.scalars(select(Game).where(Game.player_id == player_id)))
    game_ids = [g.id for g in games]
    positions = (
        list(db.scalars(select(Position).where(Position.game_id.in_(game_ids))))
        if game_ids
        else []
    )

    features = assemble_features(positions, games)

    profile = db.get(PlayerProfile, player_id)
    now = datetime.now(timezone.utc)
    if profile is None:
        profile = PlayerProfile(
            player_id=player_id,
            game_count=len(games),
            features=features,
            computed_at=now,
        )
        db.add(profile)
    else:
        profile.game_count = len(games)
        profile.features = features
        profile.computed_at = now
    db.commit()

    return features
