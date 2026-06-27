"""Unit tests for the Phase 4 digital-twin move selection.

The weight functions, softmax, temperature derivation, pattern overrides and the
python-chess flag helpers are tested in isolation (no engine). The integration
test runs the twin through 10 moves of a real game and needs Stockfish; it is
skipped automatically when no engine is available.

Run with:  pytest player_model/tests/test_twin.py
       or:  python -m player_model.tests.test_twin
"""

from __future__ import annotations

import os
import random
import tempfile

_TEST_DB = os.path.join(tempfile.gettempdir(), "pm_twin_test.db")
for _suffix in ("", "-wal", "-shm"):
    try:
        os.remove(_TEST_DB + _suffix)
    except OSError:
        pass
os.environ["PM_DATABASE_URL"] = "sqlite:///" + _TEST_DB

import chess  # noqa: E402

from player_model import twin as T  # noqa: E402


def approx(a, b, tol=1e-6):
    return a is not None and abs(a - b) <= tol


def _candidate(**kw):
    base = dict(
        move_uci="e2e4", eval_cp=20, eval_relative=20, rank=1,
        involves_tactic=False, is_sacrifice=False, is_trade=False,
        piece_moved="P", is_aggressive=False,
    )
    base.update(kw)
    return T.Candidate(**base)


# --------------------------------------------------------------------------- #
# Weight functions in isolation
# --------------------------------------------------------------------------- #
def test_eval_weight():
    prof = T.ProfileView(mean_cpl=60)            # sensitivity = 1 - 60/300 = 0.8
    c = _candidate(eval_relative=200)            # base = 2.0
    assert approx(T.eval_weight(c, prof), 1.6)

    # Very weak player -> sensitivity clamped at 0, eval ignored.
    weak = T.ProfileView(mean_cpl=400)
    assert approx(T.eval_weight(c, weak), 0.0)


def test_tactic_weight():
    prof = T.ProfileView(tactical_opportunity_conversion=0.4)
    assert approx(T.tactic_weight(_candidate(involves_tactic=True), prof), 0.8)
    assert approx(T.tactic_weight(_candidate(involves_tactic=False), prof), 0.0)


def test_sacrifice_weight():
    prof = T.ProfileView(sacrifice_tendency=0.7)   # (0.7 - 0.5) * 1.5 = 0.3
    assert approx(T.sacrifice_weight(_candidate(is_sacrifice=True), prof), 0.3)
    assert approx(T.sacrifice_weight(_candidate(is_sacrifice=False), prof), 0.0)


def test_aggression_weight():
    prof = T.ProfileView(aggression_index=0.7)     # (0.7 - 0.5) * 1.0 = 0.2
    assert approx(T.aggression_weight(_candidate(is_aggressive=True), prof), 0.2)
    assert approx(T.aggression_weight(_candidate(is_aggressive=False), prof), 0.0)


def test_trade_weight():
    prof = T.ProfileView(trade_preference_by_piece={"Q": 0.8})  # (0.8-0.5)*1.2 = 0.36
    assert approx(T.trade_weight(_candidate(is_trade=True, piece_moved="Q"), prof), 0.36)
    # Unknown piece -> default 0.5 -> zero weight.
    assert approx(T.trade_weight(_candidate(is_trade=True, piece_moved="N"), prof), 0.0)
    assert approx(T.trade_weight(_candidate(is_trade=False, piece_moved="Q"), prof), 0.0)


def test_score_candidate_sums_weights():
    prof = T.ProfileView(
        mean_cpl=60, tactical_opportunity_conversion=0.4,
        sacrifice_tendency=0.7, aggression_index=0.7,
        trade_preference_by_piece={"Q": 0.8},
    )
    c = _candidate(eval_relative=200, involves_tactic=True, is_aggressive=True)
    # 1.6 (eval) + 0.8 (tactic) + 0.2 (aggression) = 2.6
    assert approx(T.score_candidate(c, prof), 2.6)


# --------------------------------------------------------------------------- #
# Probability model
# --------------------------------------------------------------------------- #
def test_softmax_uniform_and_temperature():
    assert [round(p, 4) for p in T.softmax([1.0, 1.0], 1.0)] == [0.5, 0.5]
    # Higher score gets more mass; lower T sharpens it.
    sharp = T.softmax([2.0, 0.0], 0.3)
    warm = T.softmax([2.0, 0.0], 2.0)
    assert sharp[0] > warm[0] > 0.5
    assert approx(sum(sharp), 1.0, tol=1e-9)


def test_derive_temperature_bounds():
    assert T.derive_temperature(T.ProfileView(accuracy_variance_across_games=0)) == 0.3
    assert approx(
        T.derive_temperature(T.ProfileView(accuracy_variance_across_games=T.MAX_OBSERVED_VARIANCE)),
        2.0,
    )
    # Above the cap stays clamped at T_MAX.
    assert T.derive_temperature(T.ProfileView(accuracy_variance_across_games=999)) == 2.0


# --------------------------------------------------------------------------- #
# Pattern overrides
# --------------------------------------------------------------------------- #
class _Pat:
    def __init__(self, pattern_type, severity_score=0.5, frequency_score=0.5):
        self.pattern_type = pattern_type
        self.severity_score = severity_score
        self.frequency_score = frequency_score


def test_queen_trade_avoidance_override():
    candidates = [
        _candidate(move_uci="d2d8", is_trade=True, piece_moved="Q"),
        _candidate(move_uci="e2e4"),
    ]
    probs = [0.5, 0.5]
    out = T.apply_pattern_overrides(probs, candidates, [_Pat("queen_trade_avoidance")])
    assert out[0] < 0.5 < out[1]               # queen trade suppressed
    assert approx(sum(out), 1.0, tol=1e-9)
    # 0.5*0.1 / (0.05 + 0.5) ≈ 0.0909
    assert approx(out[0], 0.05 / 0.55, tol=1e-4)


def test_sacrifice_override_boosts():
    candidates = [_candidate(move_uci="c1h6", is_sacrifice=True), _candidate(move_uci="e2e4")]
    probs = [0.5, 0.5]
    out = T.apply_pattern_overrides(
        probs, candidates, [_Pat("high_sacrifice_tendency", frequency_score=1.0)]
    )
    assert out[0] > 0.5 > out[1]               # sacrifice boosted
    assert approx(sum(out), 1.0, tol=1e-9)


# --------------------------------------------------------------------------- #
# Flag helpers (python-chess only)
# --------------------------------------------------------------------------- #
def test_see_and_flags():
    # Winning an undefended queen with a pawn -> tactic, big positive SEE.
    board = chess.Board("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1")
    assert T._see_gain(board, chess.Move.from_uci("e4d5")) >= 150

    # Equal knight trade (recaptured by a pawn) -> SEE ~ 0, flagged as a trade.
    trade = chess.Board("4k3/2p5/3n4/8/4N3/8/8/4K3 w - - 0 1")
    mv = chess.Move.from_uci("e4d6")
    assert abs(T._see_gain(trade, mv)) < 100
    assert T._is_trade(trade, mv) is True

    # A check is aggressive.
    chk = chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 0 1")
    assert T._is_aggressive(chk, chess.Move.from_uci("a1a8")) is True


def test_get_candidates_shape_without_engine_is_empty_on_gameover():
    # Checkmate position -> no candidates, no engine call.
    mate = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert T.get_candidates(mate.fen()) == []


# --------------------------------------------------------------------------- #
# Integration: run the twin through 10 moves of a real game (needs Stockfish)
# --------------------------------------------------------------------------- #
def _engine_available() -> bool:
    try:
        from player_model.analyzer import find_stockfish

        find_stockfish()
        return True
    except Exception:
        return False


def test_integration_ten_moves():
    if not _engine_available():
        print("  (skipped: Stockfish not available)")
        return

    from player_model.engine import shutdown_engine

    pgn_moves = ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7"]
    profile = T.ProfileView(mean_cpl=40, aggression_index=0.6,
                            accuracy_variance_across_games=10)
    patterns: list = []
    rng = random.Random(42)

    board = chess.Board()
    try:
        for san in pgn_moves:
            decision = T.decide_twin_move(
                board.fen(), profile, patterns, depth=10, rng=rng
            )
            assert decision is not None
            move = chess.Move.from_uci(decision.move_uci)
            assert move in board.legal_moves            # always a legal move
            assert 0.0 <= decision.confidence <= 1.0
            assert approx(sum(decision.probs), 1.0, tol=1e-6)
            board.push(board.parse_san(san))            # advance the real game
    finally:
        shutdown_engine()
    print("  (ran 10 twin decisions against Stockfish)")


def test_integration_backtest():
    if not _engine_available():
        print("  (skipped: Stockfish not available)")
        return

    from player_model.db import SessionLocal, init_db
    from player_model.engine import shutdown_engine
    from player_model.models import Player

    init_db()
    db = SessionLocal()
    try:
        player = Player(username="twin_backtest_user")
        db.add(player)
        db.commit()  # no profile -> neutral twin

        pgn = '[Event "x"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 *\n'
        result = T.backtest_twin(player.id, pgn, db, depth=10, max_plies=8)
        assert set(result) == {
            "move_match_rate", "top3_match_rate", "cpl_correlation", "style_match_score",
        }
        for key in ("move_match_rate", "top3_match_rate", "style_match_score"):
            assert 0.0 <= result[key] <= 1.0
        assert -1.0 <= result["cpl_correlation"] <= 1.0
    finally:
        db.close()
        shutdown_engine()
    print("  (ran twin backtest against Stockfish)")


# --------------------------------------------------------------------------- #
# Direct runner
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
