"""Weakness-targeted "play-out" drill logic.

A *drill* is a position from the user's own game at the moment things went wrong,
which the user must now play out against Stockfish and either convert or hold. The
grading is deterministic and lives here as pure functions so it can be unit-tested
without a database or an engine:

- :func:`objective_for` maps a starting eval to a training objective.
- :func:`compute_verdict` maps (objective, start_eval, final_eval) to pass/fail.

The only impure helper, :func:`evaluate_final_position`, runs Stockfish on the
finished play-out to obtain the real final eval (user POV) that feeds the verdict.

All evaluations are centipawns from the *user's* point of view: positive means the
user is better. The engine reports evals from the side-to-move POV, so callers must
negate when it is the opponent's move (see :func:`evaluate_final_position`).
"""

from __future__ import annotations

import logging
from typing import Any, NamedTuple

import chess

logger = logging.getLogger(__name__)

# A play-out is capped so an attempt always terminates and the verdict reflects a
# bounded number of the user's decisions rather than a whole new game.
MAX_USER_MOVES = 12

# Objective thresholds (centipawns, user POV): clearly winning vs roughly level.
WINNING_THRESHOLD_CP = 150

# A play-out passes if the user did not let the eval slip more than this from the
# start. The same tolerance is used for every objective so "didn't throw it" is a
# single, predictable bar.
SLIP_TOLERANCE_CP = 100

# Treating a forced mate / resignation-grade eval as effectively decisive.
MATE_EVAL_CP = 100_000


class VerdictResult(NamedTuple):
    verdict: str  # "pass" | "fail"
    start_eval: int
    final_eval: int | None
    swing: int | None  # final_eval - start_eval (user POV); None if no final eval
    reason: str


def objective_for(start_eval_cp: int) -> str:
    """Classify what the user is being asked to do from this position.

    ``convert`` when clearly winning, ``hold`` when roughly level, ``defend`` when
    worse. Symmetric around 0 so the boundary is unambiguous.
    """
    if start_eval_cp >= WINNING_THRESHOLD_CP:
        return "convert"
    if start_eval_cp <= -WINNING_THRESHOLD_CP:
        return "defend"
    return "hold"


def compute_verdict(
    objective: str,
    start_eval_cp: int,
    final_eval_cp: int | None,
    *,
    mate_for_user: bool = False,
    is_draw: bool = False,
) -> VerdictResult:
    """Grade a finished play-out. Pure and deterministic.

    Pass conditions, by objective:

    - ``convert``: the user delivered mate, or the final eval stayed within
      :data:`SLIP_TOLERANCE_CP` of the start (didn't throw the win).
    - ``hold``: the final eval stayed within :data:`SLIP_TOLERANCE_CP` of the start.
    - ``defend``: the user reached a draw, or the final eval stayed within
      :data:`SLIP_TOLERANCE_CP` of the start (didn't make it worse).

    ``final_eval_cp`` is None only if the engine could not evaluate the final
    position, which always fails (we never pass without evidence).
    """
    floor = start_eval_cp - SLIP_TOLERANCE_CP
    swing = None if final_eval_cp is None else final_eval_cp - start_eval_cp
    held = final_eval_cp is not None and final_eval_cp >= floor

    if objective == "convert":
        passed = mate_for_user or held
        if mate_for_user:
            reason = "You delivered checkmate — winning position converted."
        elif passed:
            reason = "You kept the advantage and converted the position."
        else:
            reason = "You let the winning advantage slip away."
    elif objective == "hold":
        passed = held
        reason = (
            "You held the balance from a roughly level position."
            if passed
            else "The position got meaningfully worse under pressure."
        )
    elif objective == "defend":
        passed = is_draw or held
        if is_draw:
            reason = "You reached a draw from a worse position — well defended."
        elif passed:
            reason = "You defended without letting things get worse."
        else:
            reason = "The position deteriorated further from an already worse spot."
    else:  # pragma: no cover - defensive; objectives are validated upstream
        passed = held
        reason = "Position evaluated against the starting advantage."

    return VerdictResult(
        verdict="pass" if passed else "fail",
        start_eval=start_eval_cp,
        final_eval=final_eval_cp,
        swing=swing,
        reason=reason,
    )


class FinalPosition(NamedTuple):
    final_eval_cp: int | None
    mate_for_user: bool
    is_draw: bool


def evaluate_final_position(fen: str, user_color: str, *, depth: int = 14) -> FinalPosition:
    """Evaluate a finished play-out's final FEN, normalised to the user's POV.

    Returns the eval in centipawns (user POV), whether the user has just delivered
    mate, and whether the game ended in a draw. Game-over positions short-circuit
    without invoking the engine. Raises ``ValueError`` on a malformed FEN (route maps
    to 400) and ``EngineUnavailableError`` if Stockfish is missing/crashes/times out
    (route maps to 503) — these propagate untouched so the caller can tell them apart.
    """
    from stockfish_engine import StockfishEngine  # local import: root-level module

    board = chess.Board(fen)  # ValueError on bad FEN -> caller maps to 400
    user_is_white = user_color.lower().startswith("w")

    if board.is_game_over():
        outcome = board.outcome()
        if outcome is not None and outcome.winner is not None:
            user_won = outcome.winner == (chess.WHITE if user_is_white else chess.BLACK)
            return FinalPosition(
                final_eval_cp=MATE_EVAL_CP if user_won else -MATE_EVAL_CP,
                mate_for_user=user_won,
                is_draw=False,
            )
        return FinalPosition(final_eval_cp=0, mate_for_user=False, is_draw=True)

    with StockfishEngine(depth=depth) as engine:
        eval_cp, _best, _pv = engine.analyse_position(board, depth=depth, include_pv=False)

    if eval_cp is None:
        return FinalPosition(final_eval_cp=None, mate_for_user=False, is_draw=False)

    # Engine eval is from the side-to-move POV; flip to the user's POV.
    side_to_move_is_user = board.turn == (chess.WHITE if user_is_white else chess.BLACK)
    user_pov = int(eval_cp) if side_to_move_is_user else -int(eval_cp)
    return FinalPosition(final_eval_cp=user_pov, mate_for_user=False, is_draw=False)


# ── drill generation (pure mapping; persistence lives in repositories) ───────

# Phase boundaries mirror repositories.puzzles so a drill's phase matches the
# puzzle it came from.
def phase_for_move(move_number: int | None) -> str:
    n = move_number or 0
    if n <= 12:
        return "Opening"
    if n <= 30:
        return "Middlegame"
    return "Endgame"


def drill_from_puzzle(puzzle: dict[str, Any], category: str) -> dict[str, Any] | None:
    """Map a stored puzzle row (mined mistake) to a drill spec, or None if unusable.

    The puzzle's ``fen`` is the position *before* the user's mistake and its
    ``evaluation_before`` is the eval there from the user's POV (puzzles are only
    mined where the user is to move and was equal-or-better), which is exactly the
    drill's starting point.
    """
    fen = puzzle.get("fen")
    user_color = puzzle.get("color") or puzzle.get("side_to_move")
    eval_before = puzzle.get("evaluation_before")
    if eval_before is None:
        eval_before = puzzle.get("eval_before")
    if not fen or not user_color or eval_before is None:
        return None

    start_eval_cp = int(round(float(eval_before)))
    return {
        "fen": fen,
        "user_color": user_color,
        "start_eval_cp": start_eval_cp,
        "objective": objective_for(start_eval_cp),
        "category": category,
        "phase": phase_for_move(puzzle.get("move_number")),
    }


class CategorySpec(NamedTuple):
    """A training category derived from a player weakness."""

    name: str
    weakness_source: str
    phase: str | None  # "Opening" | "Middlegame" | "Endgame" | None
    opening_family: str | None


def derive_categories(insights: dict[str, Any]) -> list[CategorySpec]:
    """Turn ``get_player_insights`` output into ordered training categories.

    Consumes the insights' own weakness computations (weakest phase via
    ``mistakes.by_phase``, weakest opening family via the opening rows) rather than
    recomputing weaknesses. Most-impactful weakness first; de-duplicated.
    """
    specs: list[CategorySpec] = []
    seen: set[str] = set()

    def add(spec: CategorySpec) -> None:
        if spec.name not in seen:
            seen.add(spec.name)
            specs.append(spec)

    phase_category = {
        "Endgame": "Rook & pawn endgames",
        "Middlegame": "Converting winning middlegames",
        "Opening": "Opening accuracy",
    }

    by_phase = insights.get("mistakes", {}).get("by_phase", []) or []
    ranked = sorted((r for r in by_phase if r.get("count")), key=lambda r: -r["count"])
    for row in ranked:
        phase = row.get("category")
        name = phase_category.get(phase)
        if name:
            add(
                CategorySpec(
                    name=name,
                    weakness_source=f"Most losses in the {phase.lower()}",
                    phase=phase,
                    opening_family=None,
                )
            )

    family = _weakest_opening_family(insights)
    if family:
        add(
            CategorySpec(
                name=f"Your weak opening: {family}",
                weakness_source=f"Lowest win rate with {family}",
                phase="Opening",
                opening_family=family,
            )
        )

    if not specs:
        add(
            CategorySpec(
                name="Converting winning middlegames",
                weakness_source="Default focus",
                phase="Middlegame",
                opening_family=None,
            )
        )
    return specs


def _weakest_opening_family(insights: dict[str, Any]) -> str | None:
    openings = insights.get("openings", {})
    rows = [*openings.get("as_white", []), *openings.get("as_black", [])]
    eligible = [r for r in rows if r.get("games", 0) >= 3] or rows
    if not eligible:
        return None
    weakest = min(eligible, key=lambda r: r.get("win_rate", 100.0))
    return weakest.get("opening_family") or weakest.get("opening_name")
