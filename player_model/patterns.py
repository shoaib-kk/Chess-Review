"""Behavioural pattern detection (Phase 3).

Discovers *recurring* mistakes from a player's analysed history. A pattern is a
mistake that (1) occurs in an identifiable context, (2) recurs above a noise
threshold and (3) can be labelled in human terms.

All detection uses only stored Phase 1/2 data plus cheap python-chess board
analysis — **no new Stockfish calls**. Confidence is a binomial test against the
player's baseline blunder rate (see :func:`_confidence`).
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from typing import Optional, Sequence

import chess
from scipy.stats import binomtest

# --------------------------------------------------------------------------- #
# Tunables
# --------------------------------------------------------------------------- #
MIN_GAMES = 3                 # never emit anything below this many games
CONFIDENCE_MIN = 0.5          # suppress patterns below this confidence

# Phase boundaries (by ply).
OPENING_MAX_PLY = 20
MIDDLEGAME_MAX_PLY = 60

# Per-detector thresholds (from the spec).
HANGING_MIN_COUNT = 3
HANGING_FREQ_MULTIPLIER = 2.0
ENDGAME_MIN_GAMES = 5
ENDGAME_CPL_RATIO = 1.4
TACTIC_MIN_MISSES = 4
TACTIC_MISS_RATE = 0.4
AVOID_MIN_AVAILABLE = 5
AVOID_RATE = 0.6
OVEREXT_MIN_GAMES = 5
OVEREXT_COLLAPSE_RATE = 0.5

# Maps a mean centipawn loss onto the 0-1 severity scale (≈ one queen == 1.0).
SEVERITY_CP_SCALE = 1000.0
# A best move scoring at/above this (cp) is treated as a forced mate.
MATE_THRESHOLD = 10000

_PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}
_PIECE_NAME = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
}


# --------------------------------------------------------------------------- #
# Shared types & helpers
# --------------------------------------------------------------------------- #
@dataclass
class PlayerStats:
    total_games: int
    total_moves: int
    base_blunder_rate: float
    overall_cpl: float


@dataclass
class DetectedPattern:
    pattern_type: str
    label: str
    description: str
    severity_score: float
    frequency_score: float
    confidence: float
    sample_count: int
    supporting_game_ids: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["supporting_game_ids"] = sorted(set(self.supporting_game_ids))
        return d


def _clamp01(x: float) -> float:
    return round(max(0.0, min(1.0, x)), 4)


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


def phase_for_ply(ply: int) -> str:
    if ply <= OPENING_MAX_PLY:
        return "opening"
    if ply <= MIDDLEGAME_MAX_PLY:
        return "middlegame"
    return "endgame"


def _confidence(observed: int, trials: int, base_rate: float, sample_count: int) -> float:
    """confidence = min(sample_count/10, 1) * (1 - binomtest p-value).

    Null hypothesis: the mistake occurs at ``base_rate`` (the player's baseline).
    Observed: ``observed`` occurrences in ``trials`` context opportunities.
    ``alternative="greater"`` asks whether the contextual rate is *elevated*.
    """
    if trials <= 0 or sample_count <= 0:
        return 0.0
    p = min(max(base_rate, 1e-6), 1 - 1e-6)
    observed = min(observed, trials)
    pvalue = binomtest(observed, trials, p, alternative="greater").pvalue
    return round(min(sample_count / 10.0, 1.0) * (1 - pvalue), 4)


def _severity_from_cpl(cpls: Sequence[float]) -> float:
    if not cpls:
        return 0.0
    return _clamp01(statistics.fmean(cpls) / SEVERITY_CP_SCALE)


def player_stats(positions: Sequence, games: Sequence) -> PlayerStats:
    cpls = [p.cpl for p in positions if p.cpl is not None]
    total_moves = len(positions)
    blunders = sum(1 for p in positions if p.is_blunder)
    return PlayerStats(
        total_games=len({g.id for g in games}),
        total_moves=total_moves,
        base_blunder_rate=(blunders / total_moves) if total_moves else 0.0,
        overall_cpl=statistics.fmean(cpls) if cpls else 0.0,
    )


def _won_game(game) -> Optional[bool]:
    result = getattr(game, "result", None)
    color = getattr(game, "color_played", None)
    if not result or color not in ("white", "black"):
        return None
    if result == "1-0":
        return color == "white"
    if result == "0-1":
        return color == "black"
    return False


# --------------------------------------------------------------------------- #
# 1. Hanging-piece patterns
# --------------------------------------------------------------------------- #
def _lost_piece_type(board: chess.Board, move: chess.Move) -> Optional[int]:
    """After ``move``, return the type of the most valuable player piece left en prise.

    "En prise" = attacked by the opponent and either undefended or capturable by a
    cheaper attacker (so the opponent can win material).
    """
    player = board.turn
    after = board.copy(stack=False)
    try:
        after.push(move)
    except (AssertionError, ValueError):
        return None

    best_type: Optional[int] = None
    best_val = 0
    for sq, piece in after.piece_map().items():
        if piece.color != player or piece.piece_type == chess.KING:
            continue
        attackers = after.attackers(not player, sq)
        if not attackers:
            continue
        defenders = after.attackers(player, sq)
        cheapest = min(_PIECE_VALUES.get(after.piece_at(a).piece_type, 0) for a in attackers)
        val = _PIECE_VALUES.get(piece.piece_type, 0)
        if (not defenders or cheapest < val) and val > best_val:
            best_val = val
            best_type = piece.piece_type
    return best_type


def detect_hanging_piece_patterns(
    positions: Sequence, games: Sequence, stats: PlayerStats
) -> list[DetectedPattern]:
    # Opportunities per phase = every player move in that phase.
    phase_moves = {"opening": 0, "middlegame": 0, "endgame": 0}
    for p in positions:
        phase_moves[phase_for_ply(p.ply)] += 1

    # Tally hanging-piece blunders by (piece_type, phase).
    buckets: dict[tuple[int, str], dict] = {}
    for p in positions:
        if not p.is_blunder:
            continue
        board = _board(p.fen)
        move = _move(p.move_played)
        if board is None or move is None:
            continue
        lost = _lost_piece_type(board, move)
        if lost is None:
            continue
        key = (lost, phase_for_ply(p.ply))
        b = buckets.setdefault(key, {"cpls": [], "games": []})
        b["cpls"].append(p.cpl or 0)
        b["games"].append(p.game_id)

    patterns: list[DetectedPattern] = []
    base = stats.base_blunder_rate
    for (piece_type, phase), b in buckets.items():
        count = len(b["cpls"])
        opportunities = phase_moves[phase] or 1
        frequency = count / opportunities
        if count < HANGING_MIN_COUNT:
            continue
        if frequency <= HANGING_FREQ_MULTIPLIER * base:
            continue

        piece = _PIECE_NAME[piece_type]
        patterns.append(
            DetectedPattern(
                pattern_type=f"repeated_{piece}_loss_in_{phase}",
                label=f"Repeatedly hangs the {piece} in the {phase}",
                description=(
                    f"Lost a {piece} to an undefended/under-defended square "
                    f"{count} times during the {phase}, well above this player's "
                    f"baseline blunder rate."
                ),
                severity_score=_severity_from_cpl(b["cpls"]),
                frequency_score=_clamp01(frequency),
                confidence=_confidence(count, opportunities, base, count),
                sample_count=count,
                supporting_game_ids=b["games"],
            )
        )
    return patterns


# --------------------------------------------------------------------------- #
# 2. Endgame-weakness patterns
# --------------------------------------------------------------------------- #
def classify_endgame_type(board: chess.Board, ply: int) -> Optional[str]:
    others = {
        piece.piece_type
        for piece in board.piece_map().values()
        if piece.piece_type not in (chess.KING, chess.PAWN)
    }
    if not others:
        return "pawn_endgame" if ply > MIDDLEGAME_MAX_PLY else None
    if others == {chess.ROOK}:
        return "rook_endgame"
    if others == {chess.QUEEN}:
        return "queen_endgame"
    return None


_ENDGAME_LABEL = {
    "pawn_endgame": "pawn endgames",
    "rook_endgame": "rook endgames",
    "queen_endgame": "queen endgames",
}


def detect_endgame_weakness(
    positions: Sequence, games: Sequence, stats: PlayerStats
) -> list[DetectedPattern]:
    by_type: dict[str, dict] = {}
    for p in positions:
        board = _board(p.fen)
        if board is None or p.cpl is None:
            continue
        etype = classify_endgame_type(board, p.ply)
        if etype is None:
            continue
        t = by_type.setdefault(etype, {"cpls": [], "games": set(), "above": 0})
        t["cpls"].append(p.cpl)
        t["games"].add(p.game_id)
        if p.cpl > stats.overall_cpl:
            t["above"] += 1

    patterns: list[DetectedPattern] = []
    overall = stats.overall_cpl or 1.0
    total_games = stats.total_games or 1
    for etype, t in by_type.items():
        game_samples = len(t["games"])
        mean_cpl = statistics.fmean(t["cpls"])
        if game_samples < ENDGAME_MIN_GAMES:
            continue
        if mean_cpl <= overall * ENDGAME_CPL_RATIO:
            continue

        trials = len(t["cpls"])
        # Event = a position worse than the player's own average; null = 50/50.
        patterns.append(
            DetectedPattern(
                pattern_type=f"weakness_in_{etype}",
                label=f"Weaker in {_ENDGAME_LABEL[etype]}",
                description=(
                    f"Average centipawn loss in {_ENDGAME_LABEL[etype]} is "
                    f"{mean_cpl:.0f}, more than {ENDGAME_CPL_RATIO:g}x the overall "
                    f"average of {overall:.0f}, across {game_samples} games."
                ),
                severity_score=_severity_from_cpl(t["cpls"]),
                frequency_score=_clamp01(game_samples / total_games),
                confidence=_confidence(t["above"], trials, 0.5, game_samples),
                sample_count=game_samples,
                supporting_game_ids=list(t["games"]),
            )
        )
    return patterns


# --------------------------------------------------------------------------- #
# 3. Tactical-blindness patterns
# --------------------------------------------------------------------------- #
def classify_tactic(board: chess.Board, best_move: chess.Move) -> Optional[str]:
    """Classify the tactical motif that ``best_move`` exploits, or None.

    Only motifs that win material / force mate are returned, so a non-None result
    also satisfies the "top move is a tactic" gate.
    """
    player = board.turn
    after = board.copy(stack=False)
    try:
        after.push(best_move)
    except (AssertionError, ValueError):
        return None

    # Back-rank mate.
    if after.is_checkmate():
        enemy_king = after.king(not player)
        if enemy_king is not None and chess.square_rank(enemy_king) in (0, 7):
            return "back_rank"

    to_sq = best_move.to_square
    mover = after.piece_at(to_sq)

    # Fork: the moved piece now attacks two or more valuable enemy pieces (the
    # enemy king counts as one target when the move gives check).
    if mover is not None:
        mover_val = _PIECE_VALUES.get(mover.piece_type, 0)
        targets = 0
        for sq in after.attacks(to_sq):
            piece = after.piece_at(sq)
            if piece is None or piece.color == player:
                continue
            if piece.piece_type == chess.KING or _PIECE_VALUES.get(piece.piece_type, 0) >= mover_val:
                targets += 1
        if targets >= 2:
            return "fork"

    # Pin: an enemy piece becomes absolutely pinned that wasn't pinned before.
    for sq, piece in after.piece_map().items():
        if piece.color == player:
            continue
        if after.is_pinned(not player, sq) and not board.is_pinned(not player, sq):
            return "pin"

    # Hanging piece: best move grabs an undefended enemy piece for free.
    if board.is_capture(best_move) and not board.is_en_passant(best_move):
        if not board.attackers(not player, to_sq):
            return "hanging"

    return None


_TACTIC_LABEL = {
    "fork": "forks",
    "pin": "pins",
    "back_rank": "back-rank tactics",
    "hanging": "hanging pieces",
}


def detect_tactical_blindness(
    positions: Sequence, games: Sequence, stats: PlayerStats
) -> list[DetectedPattern]:
    seen: dict[str, dict] = {}
    for p in positions:
        board = _board(p.fen)
        best = _move(p.best_move)
        if board is None or best is None or p.eval_before is None:
            continue
        tactic = classify_tactic(board, best)
        if tactic is None:
            continue
        s = seen.setdefault(tactic, {"seen": 0, "missed": 0, "cpls": [], "games": []})
        s["seen"] += 1
        if p.move_played != p.best_move:  # didn't find the tactic
            s["missed"] += 1
            s["cpls"].append(p.cpl or 0)
            s["games"].append(p.game_id)

    patterns: list[DetectedPattern] = []
    base = stats.base_blunder_rate
    for tactic, s in seen.items():
        missed, total = s["missed"], s["seen"]
        miss_rate = missed / total if total else 0.0
        if missed < TACTIC_MIN_MISSES or miss_rate <= TACTIC_MISS_RATE:
            continue
        patterns.append(
            DetectedPattern(
                pattern_type=f"tactical_blindness_{tactic}",
                label=f"Misses {_TACTIC_LABEL[tactic]}",
                description=(
                    f"Failed to play the winning move in {missed} of {total} "
                    f"positions featuring {_TACTIC_LABEL[tactic]} "
                    f"({miss_rate:.0%} missed)."
                ),
                severity_score=_severity_from_cpl(s["cpls"]),
                frequency_score=_clamp01(miss_rate),
                confidence=_confidence(missed, total, base, missed),
                sample_count=missed,
                supporting_game_ids=s["games"],
            )
        )
    return patterns


# --------------------------------------------------------------------------- #
# 4. Avoidance patterns (queen / rook / bishop trades)
# --------------------------------------------------------------------------- #
def _trade_option(board: chess.Board, played: Optional[chess.Move], piece_type: int):
    """Return (option_exists, player_took) for an equal trade of ``piece_type``.

    An equal trade = capturing an enemy piece of the same type that is defended
    (a recapture is available).
    """
    player = board.turn
    option = took = False
    for m in board.legal_moves:
        if not board.is_capture(m) or board.is_en_passant(m):
            continue
        attacker = board.piece_at(m.from_square)
        target = board.piece_at(m.to_square)
        if attacker is None or target is None:
            continue
        if attacker.piece_type != piece_type or target.piece_type != piece_type:
            continue
        if not board.attackers(not player, m.to_square):  # undefended -> not a trade
            continue
        option = True
        if played is not None and m == played:
            took = True
    return option, took


_AVOID_PIECES = {"queen": chess.QUEEN, "rook": chess.ROOK, "bishop": chess.BISHOP}


def detect_avoidance_behaviours(
    positions: Sequence, games: Sequence, stats: PlayerStats
) -> list[DetectedPattern]:
    patterns: list[DetectedPattern] = []
    for name, piece_type in _AVOID_PIECES.items():
        available = avoided = 0
        avoided_cpls: list[float] = []
        game_ids: list[int] = []
        for p in positions:
            board = _board(p.fen)
            if board is None:
                continue
            option, took = _trade_option(board, _move(p.move_played), piece_type)
            if not option:
                continue
            available += 1
            game_ids.append(p.game_id)
            if not took:
                avoided += 1
                avoided_cpls.append(p.cpl or 0)

        if available < AVOID_MIN_AVAILABLE:
            continue
        rate = avoided / available
        if rate < AVOID_RATE:
            continue

        patterns.append(
            DetectedPattern(
                pattern_type=f"{name}_trade_avoidance",
                label=f"Avoids {name} trades",
                description=(
                    f"Declined {avoided} of {available} available {name} trades "
                    f"({rate:.0%}), suggesting a systematic preference to keep "
                    f"{name}s on the board."
                ),
                severity_score=_severity_from_cpl(avoided_cpls),
                frequency_score=_clamp01(rate),
                # Null hypothesis for avoidance: no preference (50/50).
                confidence=_confidence(avoided, available, 0.5, available),
                sample_count=available,
                supporting_game_ids=game_ids,
            )
        )
    return patterns


# --------------------------------------------------------------------------- #
# 5. Overextension patterns (kingside attacks)
# --------------------------------------------------------------------------- #
_KINGSIDE_FILES = (5, 6, 7)  # f, g, h


def _advanced_kingside_pawns(board: chess.Board, color: chess.Color) -> int:
    """Count the player's f/g/h pawns advanced to relative rank 5 or beyond."""
    count = 0
    for sq in board.pieces(chess.PAWN, color):
        if chess.square_file(sq) not in _KINGSIDE_FILES:
            continue
        rank = chess.square_rank(sq)
        rel = rank + 1 if color == chess.WHITE else 8 - rank
        if rel >= 5:
            count += 1
    return count


def detect_overextension(
    positions: Sequence, games: Sequence, stats: PlayerStats
) -> list[DetectedPattern]:
    by_game: dict[int, list] = {}
    for p in positions:
        by_game.setdefault(p.game_id, []).append(p)
    games_by_id = {g.id: g for g in games}

    attacks = collapses = 0
    collapse_games: list[int] = []
    for game_id, gps in by_game.items():
        ordered = sorted(gps, key=lambda x: x.ply)
        launch_count = 0
        launched = False
        end_advanced = 0
        for p in ordered:
            board = _board(p.fen)
            if board is None:
                continue
            adv = _advanced_kingside_pawns(board, board.turn)
            end_advanced = adv
            if adv >= 2 and not launched:
                launched = True
                launch_count = adv
        if not launched:
            continue
        attacks += 1
        won = _won_game(games_by_id.get(game_id))
        # Collapse: the attack did not win AND the advanced pawns were lost
        # (became weaknesses), i.e. fewer remain by the final stored position.
        if won is not True and end_advanced < launch_count:
            collapses += 1
            collapse_games.append(game_id)

    if attacks < OVEREXT_MIN_GAMES:
        return []
    collapse_rate = collapses / attacks
    if collapse_rate <= OVEREXT_COLLAPSE_RATE:
        return []

    total_games = stats.total_games or 1
    return [
        DetectedPattern(
            pattern_type="kingside_overextension_tendency",
            label="Overextends kingside attacks",
            description=(
                f"Launched a kingside pawn storm in {attacks} games; the attack "
                f"collapsed into weaknesses in {collapses} of them "
                f"({collapse_rate:.0%})."
            ),
            severity_score=_clamp01(collapse_rate),
            frequency_score=_clamp01(attacks / total_games),
            confidence=_confidence(collapses, attacks, 0.5, attacks),
            sample_count=attacks,
            supporting_game_ids=collapse_games,
        )
    ]


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
_DETECTORS = (
    detect_hanging_piece_patterns,
    detect_endgame_weakness,
    detect_tactical_blindness,
    detect_avoidance_behaviours,
    detect_overextension,
)


def detect_all_patterns(positions: Sequence, games: Sequence) -> list[DetectedPattern]:
    """Run every detector over in-memory rows and return surviving patterns.

    Applies the global gates (≥3 games, confidence ≥ 0.5) and deduplicates by
    ``pattern_type`` (keeping the strongest by severity × confidence). Split out
    from :func:`compute_behavioural_patterns` so it is unit-testable without a DB.
    """
    if len({g.id for g in games}) < MIN_GAMES:
        return []

    stats = player_stats(positions, games)

    candidates: list[DetectedPattern] = []
    for detector in _DETECTORS:
        candidates.extend(detector(positions, games, stats))

    # Dedup: strongest instance of each pattern_type wins.
    best: dict[str, DetectedPattern] = {}
    for pat in candidates:
        if pat.confidence < CONFIDENCE_MIN:
            continue
        score = pat.severity_score * pat.confidence
        cur = best.get(pat.pattern_type)
        if cur is None or score > cur.severity_score * cur.confidence:
            best[pat.pattern_type] = pat

    return sorted(
        best.values(),
        key=lambda p: p.severity_score * p.confidence,
        reverse=True,
    )


def compute_behavioural_patterns(player_id: int, db) -> list[dict]:
    """Detect patterns for a player and persist them (delete + reinsert).

    Returns the list of pattern dicts, sorted by severity × confidence DESC.
    """
    from sqlalchemy import delete, select

    from .models import BehaviouralPattern, Game, Position

    games = list(db.scalars(select(Game).where(Game.player_id == player_id)))
    game_ids = [g.id for g in games]
    positions = (
        list(db.scalars(select(Position).where(Position.game_id.in_(game_ids))))
        if game_ids
        else []
    )

    patterns = detect_all_patterns(positions, games)

    db.execute(
        delete(BehaviouralPattern).where(BehaviouralPattern.player_id == player_id)
    )
    for pat in patterns:
        db.add(BehaviouralPattern(player_id=player_id, **pat.to_dict()))
    db.commit()

    return [pat.to_dict() for pat in patterns]
