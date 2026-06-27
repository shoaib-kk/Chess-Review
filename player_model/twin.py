"""Digital Twin move selection (Phase 4).

Given a position, generate a move that authentically mimics how a specific player
would respond — not always the best move, but the most *characteristic* one.

Pipeline:
1. Stockfish produces the top-N candidates (a single engine call per request).
2. Each candidate is scored against the player's profile (pure Python).
3. A softmax with a player-derived temperature gives a probability distribution.
4. Behavioural-pattern overrides reshape the distribution.
5. A move is sampled from it.

The scoring layer adapts the Phase 2 feature blob (nested JSON, some values on a
centipawn scale) onto the flat 0-1 ``profile`` the spec's weight formulas assume —
see :class:`ProfileView`.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional, Sequence

import chess
import chess.engine

from . import patterns as patterns_mod
from .engine import ENGINE_LOCK as _ENGINE_LOCK, get_engine

# --------------------------------------------------------------------------- #
# Tunables
# --------------------------------------------------------------------------- #
DEFAULT_CANDIDATES = 5
DEFAULT_DEPTH = 16
TACTIC_GAIN_CP = 150          # material gain that marks a candidate as a tactic
SAC_GIVE_CP = 100             # material given up to count as a sacrifice
SAC_EVAL_TOLERANCE = 50       # position may not worsen by more than this (cp)
# Maps the Phase 2 aggression_index (mean |eval| in cp) onto 0-1 for the formula.
AGGRESSION_CP_SCALE = 200.0
# Similarity prior (Phase 5).
SIMILARITY_BLEND_DIST = 0.15   # blend in the similarity prior below this distance
SIMILARITY_FALLBACK_DIST = 0.3  # above this, model-only (documented Phase 4 fallback)
SIM_MODEL_WEIGHT = 0.6
SIM_PRIOR_WEIGHT = 0.4
SIM_TOP_K = 5
# Temperature derivation: variance at/above this maps to T = 2.0.
MAX_OBSERVED_VARIANCE = 25.0
T_MIN, T_MAX = 0.3, 2.0

# SEE piece values (centipawns).
_SEE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}
# Coarse values for "equal-value" trade detection (minor pieces equal).
_TRADE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}

# SimpleEngine is not thread-safe; access is serialised through the shared
# ``engine.ENGINE_LOCK`` (imported above) so twin moves and inline ingestion in
# the same process never talk to Stockfish concurrently.


# --------------------------------------------------------------------------- #
# Data types
# --------------------------------------------------------------------------- #
@dataclass
class Candidate:
    move_uci: str
    eval_cp: int          # centipawns, White's perspective
    eval_relative: int    # centipawns, side-to-move's perspective
    rank: int             # 1 = best
    involves_tactic: bool
    is_sacrifice: bool
    is_trade: bool
    piece_moved: str      # P/N/B/R/Q/K
    is_aggressive: bool


@dataclass
class ProfileView:
    """Flat, 0-1 adapter over the stored Phase 2 feature blob."""

    mean_cpl: float = 50.0
    accuracy_variance_across_games: float = 0.0
    tactical_opportunity_conversion: float = 0.3
    sacrifice_tendency: float = 0.5
    aggression_index: float = 0.5  # already normalised to 0-1
    trade_preference_by_piece: dict = field(default_factory=dict)

    @classmethod
    def from_features(cls, features: Optional[dict]) -> "ProfileView":
        f = features or {}
        acc = f.get("accuracy") or {}
        tac = f.get("tactical") or {}
        sty = f.get("style") or {}

        def num(d, key, default):
            v = d.get(key)
            return float(v) if v is not None else default

        raw_aggr = sty.get("aggression_index")
        aggr = (
            _clamp01(float(raw_aggr) / AGGRESSION_CP_SCALE)
            if raw_aggr is not None
            else 0.5
        )

        trade_pref_raw = sty.get("trade_preference_by_piece") or {}
        trade_pref = {
            k: (float(v) if v is not None else 0.5) for k, v in trade_pref_raw.items()
        }

        return cls(
            mean_cpl=num(acc, "mean_cpl", 50.0),
            accuracy_variance_across_games=num(acc, "accuracy_variance_across_games", 0.0),
            tactical_opportunity_conversion=num(tac, "tactical_opportunity_conversion", 0.3),
            sacrifice_tendency=num(tac, "sacrifice_tendency", 0.5),
            aggression_index=aggr,
            trade_preference_by_piece=trade_pref,
        )


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# --------------------------------------------------------------------------- #
# Flag computation (python-chess only)
# --------------------------------------------------------------------------- #
def _see_gain(board: chess.Board, move: chess.Move) -> int:
    """Static exchange evaluation on ``move``'s target square (cp, mover POV).

    Plays out the capture sequence with the least-valuable attacker each time on a
    mutated board copy — removing pieces reveals x-ray attackers naturally. Quiet
    moves return a negative value when the piece is left hanging, 0 when safe.
    """
    to_sq = move.to_square
    b = board.copy(stack=False)
    side = board.turn

    if board.is_en_passant(move):
        captured_val = _SEE_VALUES[chess.PAWN]
        b.remove_piece_at(to_sq + (-8 if side == chess.WHITE else 8))
    else:
        target = board.piece_at(to_sq)
        captured_val = _SEE_VALUES[target.piece_type] if target else 0

    mover = board.piece_at(move.from_square)
    if mover is None:
        return 0
    piece_on_sq = move.promotion or mover.piece_type
    promo_bonus = (
        _SEE_VALUES[move.promotion] - _SEE_VALUES[chess.PAWN] if move.promotion else 0
    )

    b.remove_piece_at(move.from_square)
    b.remove_piece_at(to_sq)
    b.set_piece_at(to_sq, chess.Piece(piece_on_sq, side))

    gains = [captured_val + promo_bonus]
    val_on_sq = _SEE_VALUES[piece_on_sq]
    cur = not side
    while True:
        attackers = b.attackers(cur, to_sq)
        if not attackers:
            break
        lva_sq = min(attackers, key=lambda s: _SEE_VALUES[b.piece_at(s).piece_type])
        lva_type = b.piece_at(lva_sq).piece_type
        gains.append(val_on_sq - gains[-1])
        b.remove_piece_at(lva_sq)
        b.remove_piece_at(to_sq)
        b.set_piece_at(to_sq, chess.Piece(lva_type, cur))
        val_on_sq = _SEE_VALUES[lva_type]
        cur = not cur

    for i in range(len(gains) - 1, 0, -1):
        gains[i - 1] = -max(-gains[i - 1], gains[i])
    return gains[0]


def _is_trade(board: chess.Board, move: chess.Move) -> bool:
    if not board.is_capture(move):
        return False
    mover = board.piece_at(move.from_square)
    if board.is_en_passant(move):
        captured_type = chess.PAWN
    else:
        target = board.piece_at(move.to_square)
        captured_type = target.piece_type if target else None
    if mover is None or captured_type is None:
        return False
    return _TRADE_VALUES[mover.piece_type] == _TRADE_VALUES[captured_type]


def _is_aggressive(board: chess.Board, move: chess.Move) -> bool:
    player = board.turn
    after = board.copy(stack=False)
    after.push(move)

    if after.is_check():  # immediate threat to the king
        return True

    to_sq = move.to_square
    for sq in after.attacks(to_sq):  # creates a threat on an undefended enemy piece
        piece = after.piece_at(sq)
        if piece and piece.color != player and not after.attackers(not player, sq):
            return True

    enemy_king = board.king(not player)
    if enemy_king is not None:
        closer = chess.square_distance(to_sq, enemy_king) < chess.square_distance(
            move.from_square, enemy_king
        )
        rank = chess.square_rank(to_sq)
        rel = rank + 1 if player == chess.WHITE else 8 - rank
        if closer and rel >= 5:
            return True
    return False


# --------------------------------------------------------------------------- #
# 1. Candidate generation (one Stockfish call)
# --------------------------------------------------------------------------- #
def get_candidates(
    fen: str, n: int = DEFAULT_CANDIDATES, depth: int = DEFAULT_DEPTH
) -> list[Candidate]:
    board = chess.Board(fen)
    if board.is_game_over():
        return []

    with _ENGINE_LOCK:
        engine = get_engine()
        infos = engine.analyse(
            board, chess.engine.Limit(depth=depth), multipv=n
        )
    if isinstance(infos, dict):
        infos = [infos]

    mover = board.turn
    candidates: list[Candidate] = []
    raw = []  # (move, eval_relative)
    for rank, info in enumerate(infos, start=1):
        pv = info.get("pv")
        if not pv:
            continue
        move = pv[0]
        eval_rel = info["score"].pov(mover).score(mate_score=100000)
        raw.append((move, eval_rel, rank))

    if not raw:
        return []
    best_eval = raw[0][1]

    for move, eval_rel, rank in raw:
        see = _see_gain(board, move)
        piece = board.piece_at(move.from_square)
        eval_white = eval_rel if mover == chess.WHITE else -eval_rel
        is_sacrifice = see <= -SAC_GIVE_CP and eval_rel >= best_eval - SAC_EVAL_TOLERANCE
        candidates.append(
            Candidate(
                move_uci=move.uci(),
                eval_cp=int(eval_white),
                eval_relative=int(eval_rel),
                rank=rank,
                involves_tactic=see >= TACTIC_GAIN_CP,
                is_sacrifice=is_sacrifice,
                is_trade=_is_trade(board, move),
                piece_moved=piece.symbol().upper() if piece else "?",
                is_aggressive=_is_aggressive(board, move),
            )
        )
    return candidates


# --------------------------------------------------------------------------- #
# 2. Scoring (one function per weight, exactly per spec)
# --------------------------------------------------------------------------- #
def eval_weight(candidate: Candidate, profile: ProfileView) -> float:
    base = candidate.eval_relative / 100
    # Lower skill (higher mean_cpl) -> less eval-driven. Clamped to avoid inversion.
    eval_sensitivity = max(0.0, 1 - (profile.mean_cpl / 300))
    return base * eval_sensitivity


def tactic_weight(candidate: Candidate, profile: ProfileView) -> float:
    if candidate.involves_tactic:
        return profile.tactical_opportunity_conversion * 2.0
    return 0.0


def sacrifice_weight(candidate: Candidate, profile: ProfileView) -> float:
    if candidate.is_sacrifice:
        return (profile.sacrifice_tendency - 0.5) * 1.5
    return 0.0


def aggression_weight(candidate: Candidate, profile: ProfileView) -> float:
    if candidate.is_aggressive:
        return (profile.aggression_index - 0.5) * 1.0
    return 0.0


def trade_weight(candidate: Candidate, profile: ProfileView) -> float:
    if candidate.is_trade:
        preference = profile.trade_preference_by_piece.get(candidate.piece_moved, 0.5)
        return (preference - 0.5) * 1.2
    return 0.0


def score_candidate(candidate: Candidate, profile: ProfileView) -> float:
    return (
        eval_weight(candidate, profile)
        + tactic_weight(candidate, profile)
        + sacrifice_weight(candidate, profile)
        + aggression_weight(candidate, profile)
        + trade_weight(candidate, profile)
    )


# --------------------------------------------------------------------------- #
# 3. Probability model
# --------------------------------------------------------------------------- #
def softmax(scores: Sequence[float], T: float = 1.0) -> list[float]:
    if not scores:
        return []
    T = max(1e-6, T)
    m = max(scores)
    exps = [math.exp((s - m) / T) for s in scores]
    total = sum(exps)
    if total <= 0:
        return [1.0 / len(scores)] * len(scores)
    return [e / total for e in exps]


def derive_temperature(profile: ProfileView) -> float:
    var = profile.accuracy_variance_across_games or 0.0
    T = T_MIN + (var / MAX_OBSERVED_VARIANCE) * (T_MAX - T_MIN)
    return max(T_MIN, min(T_MAX, T))


# --------------------------------------------------------------------------- #
# 4. Behavioural pattern overrides
# --------------------------------------------------------------------------- #
def _renormalise(probs: list[float]) -> list[float]:
    total = sum(probs)
    if total <= 0:
        return [1.0 / len(probs)] * len(probs)
    return [p / total for p in probs]


def apply_pattern_overrides(
    probs: list[float],
    candidates: Sequence[Candidate],
    patterns: Sequence,
    board: Optional[chess.Board] = None,
) -> list[float]:
    """Reshape ``probs`` according to the player's active behavioural patterns."""
    probs = list(probs)
    if not probs:
        return probs

    for pat in patterns:
        ptype = getattr(pat, "pattern_type", None) or (
            pat.get("pattern_type") if isinstance(pat, dict) else None
        )
        severity = _attr(pat, "severity_score", 0.0)
        frequency = _attr(pat, "frequency_score", 0.0)
        if not ptype:
            continue

        if ptype == "queen_trade_avoidance":
            for i, c in enumerate(candidates):
                if c.is_trade and c.piece_moved == "Q":
                    probs[i] *= 0.1
            probs = _renormalise(probs)

        elif ptype.startswith("tactical_blindness_"):
            tactic_type = ptype[len("tactical_blindness_"):]
            top_i = min(range(len(candidates)), key=lambda i: candidates[i].rank)
            if board is not None:
                move = chess.Move.from_uci(candidates[top_i].move_uci)
                if patterns_mod.classify_tactic(board, move) == tactic_type:
                    probs[top_i] *= (1 - severity)
                    probs = _renormalise(probs)

        elif "sacrifice" in ptype:  # high sacrifice tendency
            changed = False
            for i, c in enumerate(candidates):
                if c.is_sacrifice:
                    probs[i] *= (1 + frequency)
                    changed = True
            if changed:
                probs = _renormalise(probs)

    return probs


def _attr(obj, name, default):
    if isinstance(obj, dict):
        v = obj.get(name, default)
    else:
        v = getattr(obj, name, default)
    return default if v is None else v


# --------------------------------------------------------------------------- #
# 5. Move selection
# --------------------------------------------------------------------------- #
def sample_from_distribution(
    candidates: Sequence[Candidate],
    probs: Sequence[float],
    rng: Optional[random.Random] = None,
) -> int:
    rng = rng or random
    return rng.choices(range(len(candidates)), weights=probs, k=1)[0]


@dataclass
class TwinDecision:
    candidates: list[Candidate]
    probs: list[float]
    selected_index: int

    @property
    def move_uci(self) -> str:
        return self.candidates[self.selected_index].move_uci

    @property
    def confidence(self) -> float:
        return round(self.probs[self.selected_index], 4)


def _sp_distance(sp) -> float:
    return sp["distance"] if isinstance(sp, dict) else sp.distance


def _sp_move(sp) -> str:
    return sp["move_played"] if isinstance(sp, dict) else sp.move_played


def similarity_prior(
    candidates: Sequence[Candidate], similar: Sequence
) -> Optional[list[float]]:
    """Distribution over candidates from similar positions, weighted by 1/distance.

    Returns ``None`` when none of the similar moves are playable candidates.
    """
    by_move: dict[str, float] = {}
    for sp in similar:
        by_move[_sp_move(sp)] = by_move.get(_sp_move(sp), 0.0) + 1.0 / (
            _sp_distance(sp) + 1e-6
        )
    weights = [by_move.get(c.move_uci, 0.0) for c in candidates]
    total = sum(weights)
    if total <= 0:
        return None
    return [w / total for w in weights]


def decide_twin_move(
    fen: str,
    profile: ProfileView,
    patterns: Sequence,
    *,
    n: int = DEFAULT_CANDIDATES,
    depth: int = DEFAULT_DEPTH,
    rng: Optional[random.Random] = None,
    argmax: bool = False,
    similar_positions: Optional[Sequence] = None,
) -> Optional[TwinDecision]:
    """Pure decision step given an already-loaded profile, patterns and (optional)
    similar positions for the Phase 5 similarity prior."""
    candidates = get_candidates(fen, n=n, depth=depth)
    if not candidates:
        return None

    board = chess.Board(fen)
    scores = [score_candidate(c, profile) for c in candidates]
    probs = softmax(scores, T=derive_temperature(profile))
    probs = apply_pattern_overrides(probs, candidates, patterns, board)

    # Phase 5: blend a similarity prior when a close historical match exists.
    if similar_positions:
        closest = min(_sp_distance(sp) for sp in similar_positions)
        if closest < SIMILARITY_BLEND_DIST:
            prior = similarity_prior(candidates, list(similar_positions)[:SIM_TOP_K])
            if prior is not None:
                probs = [
                    SIM_MODEL_WEIGHT * m + SIM_PRIOR_WEIGHT * s
                    for m, s in zip(probs, prior)
                ]
                probs = _renormalise(probs)

    if argmax:
        idx = max(range(len(probs)), key=lambda i: probs[i])
    else:
        idx = sample_from_distribution(candidates, probs, rng)
    return TwinDecision(candidates=candidates, probs=probs, selected_index=idx)


def load_player_profile(player_id: int, db) -> ProfileView:
    from .models import PlayerProfile

    row = db.get(PlayerProfile, player_id)
    return ProfileView.from_features(row.features if row else None)


def load_behavioural_patterns(player_id: int, db) -> list:
    from sqlalchemy import select

    from .models import BehaviouralPattern

    return list(
        db.scalars(
            select(BehaviouralPattern).where(BehaviouralPattern.player_id == player_id)
        )
    )


def load_similar_positions(fen: str, player_id: int, k: int = 10) -> list:
    """Best-effort similarity lookup; returns [] if no index exists or faiss errors."""
    try:
        from .index_manager import find_similar_positions

        return find_similar_positions(fen, player_id, k=k)
    except Exception:
        return []


def decide_for_player(
    fen: str,
    player_id: int,
    db,
    *,
    rng: Optional[random.Random] = None,
    argmax: bool = False,
    n: int = DEFAULT_CANDIDATES,
    depth: int = DEFAULT_DEPTH,
) -> Optional[TwinDecision]:
    """Full pipeline: load profile, patterns and the similarity prior, then decide."""
    profile = load_player_profile(player_id, db)
    patterns = load_behavioural_patterns(player_id, db)
    similar = load_similar_positions(fen, player_id)
    return decide_twin_move(
        fen, profile, patterns, rng=rng, argmax=argmax, n=n, depth=depth,
        similar_positions=similar,
    )


def select_twin_move(
    fen: str, player_id: int, db, *, rng: Optional[random.Random] = None
) -> Optional[str]:
    """Full pipeline: load profile + patterns + similarity prior; return a UCI move."""
    decision = decide_for_player(fen, player_id, db, rng=rng)
    return decision.move_uci if decision else None


# --------------------------------------------------------------------------- #
# 7. Backtest
# --------------------------------------------------------------------------- #
def _statistics_correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    import statistics

    if len(xs) < 2 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return 0.0
    try:
        return round(statistics.correlation(xs, ys), 4)
    except statistics.StatisticsError:
        return 0.0


def backtest_twin(
    player_id: int,
    game_pgn: str,
    db,
    *,
    depth: int = DEFAULT_DEPTH,
    max_plies: int = 40,
) -> dict:
    """Run the twin through a real game and compare to the actual moves played.

    Uses argmax (deterministic) for the match metrics. Per position this calls
    Stockfish for the candidates and, when the actual move isn't among them, once
    more to score the actual move for the CPL correlation.
    """
    import io

    import chess.pgn

    profile = load_player_profile(player_id, db)
    patterns = load_behavioural_patterns(player_id, db)

    game = chess.pgn.read_game(io.StringIO(game_pgn))
    if game is None:
        return _empty_backtest()

    board = game.board()
    total = matches = top3_hits = 0
    twin_cpls: list[float] = []
    player_cpls: list[float] = []

    for actual in game.mainline_moves():
        if total >= max_plies:
            break
        fen = board.fen()
        similar = load_similar_positions(fen, player_id)
        decision = decide_twin_move(
            fen, profile, patterns, depth=depth, argmax=True, similar_positions=similar
        )
        if decision is None:
            board.push(actual)
            continue

        total += 1
        actual_uci = actual.uci()
        by_prob = sorted(
            range(len(decision.candidates)), key=lambda i: decision.probs[i], reverse=True
        )
        predicted_uci = decision.candidates[by_prob[0]].move_uci
        if predicted_uci == actual_uci:
            matches += 1
        top3 = {decision.candidates[i].move_uci for i in by_prob[:3]}
        if actual_uci in top3:
            top3_hits += 1

        best_eval = max(c.eval_relative for c in decision.candidates)
        twin_eval = decision.candidates[by_prob[0]].eval_relative
        actual_eval = _actual_move_eval(board, actual, decision.candidates, depth)
        if actual_eval is not None:
            twin_cpls.append(max(0, best_eval - twin_eval))
            player_cpls.append(max(0, best_eval - actual_eval))

        board.push(actual)

    if total == 0:
        return _empty_backtest()

    move_match = round(matches / total, 4)
    top3_match = round(top3_hits / total, 4)
    corr = _statistics_correlation(twin_cpls, player_cpls)
    style = round(
        _clamp01(0.4 * move_match + 0.3 * top3_match + 0.3 * max(0.0, corr)), 4
    )
    return {
        "move_match_rate": move_match,
        "top3_match_rate": top3_match,
        "cpl_correlation": corr,
        "style_match_score": style,
    }


def _actual_move_eval(
    board: chess.Board, move: chess.Move, candidates: Sequence[Candidate], depth: int
) -> Optional[int]:
    for c in candidates:
        if c.move_uci == move.uci():
            return c.eval_relative
    mover = board.turn
    after = board.copy(stack=False)
    after.push(move)
    with _ENGINE_LOCK:
        engine = get_engine()
        info = engine.analyse(after, chess.engine.Limit(depth=depth))
    # After the push it's the opponent to move; flip back to the mover's POV.
    return int(info["score"].pov(mover).score(mate_score=100000))


def _empty_backtest() -> dict:
    return {
        "move_match_rate": 0.0,
        "top3_match_rate": 0.0,
        "cpl_correlation": 0.0,
        "style_match_score": 0.0,
    }
