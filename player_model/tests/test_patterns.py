"""Unit tests for the Phase 3 behavioural pattern detectors.

Each detector is exercised with synthetic position/game data. A final test runs
the orchestrator against a temporary SQLite database.

Run with:  pytest player_model/tests/test_patterns.py
       or:  python -m player_model.tests.test_patterns
"""

from __future__ import annotations

import os
import tempfile

_TEST_DB = os.path.join(tempfile.gettempdir(), "pm_patterns_test.db")
for _suffix in ("", "-wal", "-shm"):
    try:
        os.remove(_TEST_DB + _suffix)
    except OSError:
        pass
os.environ["PM_DATABASE_URL"] = "sqlite:///" + _TEST_DB

import chess  # noqa: E402

from player_model import patterns as P  # noqa: E402

STARTING_FEN = chess.STARTING_FEN


# --------------------------------------------------------------------------- #
# Stand-ins for ORM rows
# --------------------------------------------------------------------------- #
class Pos:
    def __init__(self, **kw):
        self.game_id = kw.get("game_id", 1)
        self.ply = kw.get("ply", 1)
        self.fen = kw.get("fen", STARTING_FEN)
        self.move_played = kw.get("move_played", "e2e4")
        self.best_move = kw.get("best_move", "e2e4")
        self.eval_before = kw.get("eval_before", 20)
        self.eval_after = kw.get("eval_after", 20)
        self.cpl = kw.get("cpl", 10)
        self.is_mistake = kw.get("is_mistake", False)
        self.is_blunder = kw.get("is_blunder", False)
        self.is_brilliant = kw.get("is_brilliant", False)
        self.clock_seconds = kw.get("clock_seconds", None)
        self.candidate_evals = kw.get("candidate_evals", None)


class Gm:
    def __init__(self, id, result="1-0", color_played="white", pgn_raw=""):
        self.id = id
        self.result = result
        self.color_played = color_played
        self.pgn_raw = pgn_raw


def approx(a, b, tol=1e-3):
    return a is not None and abs(a - b) <= tol


def _stats(positions, games):
    return P.player_stats(positions, games)


def _find(patterns, pattern_type):
    return next((p for p in patterns if p.pattern_type == pattern_type), None)


# --------------------------------------------------------------------------- #
# Confidence helper & tactic/endgame classifiers (building blocks)
# --------------------------------------------------------------------------- #
def test_confidence_scoring():
    # Strong, well-sampled signal -> high confidence.
    assert P._confidence(7, 10, 0.5, 10) > 0.5
    # Only 3 samples -> capped at min(3/10,1)=0.3 -> always suppressed.
    assert P._confidence(3, 3, 0.1, 3) < 0.5
    assert P._confidence(0, 0, 0.5, 0) == 0.0


def test_classify_endgame_type():
    rook = chess.Board("4k3/r7/8/8/8/8/R7/4K3 w - - 0 65")
    assert P.classify_endgame_type(rook, 65) == "rook_endgame"
    queen = chess.Board("3qk3/8/8/8/8/8/3Q4/3K4 w - - 0 65")
    assert P.classify_endgame_type(queen, 65) == "queen_endgame"
    pawns = chess.Board("4k3/5ppp/8/8/8/8/5PPP/4K3 w - - 0 70")
    assert P.classify_endgame_type(pawns, 70) == "pawn_endgame"
    assert P.classify_endgame_type(pawns, 40) is None  # ply gate for pawn endgame
    assert P.classify_endgame_type(chess.Board(), 10) is None


def test_classify_tactic():
    # Knight fork of king + queen.
    fork = chess.Board("q3k3/8/4N3/8/8/8/8/4K3 w - - 0 25")
    assert P.classify_tactic(fork, chess.Move.from_uci("e6c7")) == "fork"
    # Free capture of an undefended piece.
    hanging = chess.Board("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 20")
    assert P.classify_tactic(hanging, chess.Move.from_uci("e4d5")) == "hanging"


# --------------------------------------------------------------------------- #
# 1. Hanging piece
# --------------------------------------------------------------------------- #
HANG_FEN = "4k3/8/5p2/8/8/8/3Q4/4K3 w - - 0 30"  # Qg5?? walks into the f6 pawn


def _hanging_dataset():
    positions = []
    # 6 queen blunders in the middlegame, spread across 3 games.
    for i in range(6):
        positions.append(Pos(game_id=(i % 3) + 1, ply=30, fen=HANG_FEN,
                             move_played="d2g5", is_blunder=True, cpl=900))
    # 30 quiet opening moves dilute the baseline blunder rate.
    for i in range(30):
        positions.append(Pos(game_id=(i % 3) + 1, ply=10, cpl=10))
    return positions, [Gm(1), Gm(2), Gm(3)]


def test_detect_hanging_piece():
    positions, games = _hanging_dataset()
    out = P.detect_hanging_piece_patterns(positions, games, _stats(positions, games))
    pat = _find(out, "repeated_queen_loss_in_middlegame")
    assert pat is not None
    assert pat.sample_count == 6
    assert pat.severity_score > 0
    assert pat.confidence > 0.5
    assert set(pat.supporting_game_ids) == {1, 2, 3}


# --------------------------------------------------------------------------- #
# 2. Endgame weakness
# --------------------------------------------------------------------------- #
ROOK_FEN = "4k3/r7/8/8/8/8/R7/4K3 w - - 0 65"


def _endgame_dataset():
    positions = []
    for g in range(1, 7):  # 6 games, 2 rook-endgame positions each
        positions.append(Pos(game_id=g, ply=65, fen=ROOK_FEN, cpl=150))
        positions.append(Pos(game_id=g, ply=70, fen=ROOK_FEN, cpl=150))
        positions.append(Pos(game_id=g, ply=30, fen=STARTING_FEN, cpl=20))  # filler
    games = [Gm(g) for g in range(1, 7)]
    return positions, games


def test_detect_endgame_weakness():
    positions, games = _endgame_dataset()
    out = P.detect_endgame_weakness(positions, games, _stats(positions, games))
    pat = _find(out, "weakness_in_rook_endgame")
    assert pat is not None
    assert pat.sample_count == 6  # game samples
    assert pat.confidence > 0.5
    assert pat.severity_score > 0


# --------------------------------------------------------------------------- #
# 3. Tactical blindness
# --------------------------------------------------------------------------- #
FORK_FEN = "q3k3/8/4N3/8/8/8/8/4K3 w - - 0 25"  # Nc7+ forks king & queen


def _tactical_dataset():
    positions = []
    for i in range(6):  # 6 missed forks across 3 games
        positions.append(Pos(game_id=(i % 3) + 1, ply=25, fen=FORK_FEN,
                             best_move="e6c7", move_played="e1d1",
                             eval_before=400, cpl=400))
    return positions, [Gm(1), Gm(2), Gm(3)]


def test_detect_tactical_blindness():
    positions, games = _tactical_dataset()
    out = P.detect_tactical_blindness(positions, games, _stats(positions, games))
    pat = _find(out, "tactical_blindness_fork")
    assert pat is not None
    assert pat.sample_count == 6
    assert approx(pat.frequency_score, 1.0)  # all missed
    assert pat.confidence > 0.5


# --------------------------------------------------------------------------- #
# 4. Avoidance
# --------------------------------------------------------------------------- #
QTRADE_FEN = "3qk3/8/8/8/8/8/3Q4/3K4 w - - 0 30"  # Qxd8 is an equal trade


def _avoidance_dataset():
    positions = []
    for i in range(7):  # declined
        positions.append(Pos(game_id=(i % 3) + 1, fen=QTRADE_FEN, move_played="d1c1"))
    for i in range(3):  # accepted
        positions.append(Pos(game_id=(i % 3) + 1, fen=QTRADE_FEN, move_played="d2d8"))
    return positions, [Gm(1), Gm(2), Gm(3)]


def test_detect_avoidance():
    positions, games = _avoidance_dataset()
    out = P.detect_avoidance_behaviours(positions, games, _stats(positions, games))
    pat = _find(out, "queen_trade_avoidance")
    assert pat is not None
    assert pat.sample_count == 10  # available opportunities
    assert approx(pat.frequency_score, 0.7)
    assert pat.confidence > 0.5
    # No rook/bishop trade options existed.
    assert _find(out, "rook_trade_avoidance") is None
    assert _find(out, "bishop_trade_avoidance") is None


# --------------------------------------------------------------------------- #
# 5. Overextension
# --------------------------------------------------------------------------- #
LAUNCH_FEN = "4k3/8/8/5PP1/8/8/8/4K3 w - - 0 30"  # f5,g5 pawns advanced
COLLAPSE_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 60"   # attacking pawns gone


def _overextension_dataset():
    positions = []
    games = []
    for g in range(1, 7):  # 6 games: launch then collapse, all lost
        positions.append(Pos(game_id=g, ply=30, fen=LAUNCH_FEN))
        positions.append(Pos(game_id=g, ply=60, fen=COLLAPSE_FEN))
        games.append(Gm(g, result="0-1", color_played="white"))
    return positions, games


def test_detect_overextension():
    positions, games = _overextension_dataset()
    out = P.detect_overextension(positions, games, _stats(positions, games))
    pat = _find(out, "kingside_overextension_tendency")
    assert pat is not None
    assert pat.sample_count == 6
    assert approx(pat.severity_score, 1.0)  # all collapsed
    assert pat.confidence > 0.5


# --------------------------------------------------------------------------- #
# Orchestrator / global gates
# --------------------------------------------------------------------------- #
def test_min_games_gate():
    # Two games only -> nothing emitted regardless of signal.
    positions, _ = _avoidance_dataset()
    games = [Gm(1), Gm(2)]
    for p in positions:
        p.game_id = (positions.index(p) % 2) + 1
    assert P.detect_all_patterns(positions, games) == []


def test_detect_all_dedup_and_sort():
    positions, games = _avoidance_dataset()
    out = P.detect_all_patterns(positions, games)
    assert len(out) >= 1
    # Sorted by severity * confidence DESC.
    scores = [p.severity_score * p.confidence for p in out]
    assert scores == sorted(scores, reverse=True)
    # No duplicate pattern_types.
    types = [p.pattern_type for p in out]
    assert len(types) == len(set(types))


def test_compute_behavioural_patterns_orchestrator():
    from player_model.db import SessionLocal, init_db
    from player_model.models import BehaviouralPattern, Game, Player, Position
    from player_model.patterns import compute_behavioural_patterns

    init_db()
    db = SessionLocal()
    try:
        player = Player(username="pattern_test_user")
        db.add(player)
        db.flush()

        for g in range(3):
            game = Game(
                player_id=player.id, pgn_raw="", pgn_hash=f"hash-pat-{g}",
                color_played="white", result="1-0",
            )
            db.add(game)
            db.flush()
            # 4 declined queen trades per game -> 12 available, all declined.
            for i in range(4):
                db.add(Position(
                    game_id=game.id, ply=30 + i, fen=QTRADE_FEN,
                    move_played="d1c1", best_move="d2d8", eval_before=0, cpl=15,
                ))
        db.commit()

        result = compute_behavioural_patterns(player.id, db)
        assert any(p["pattern_type"] == "queen_trade_avoidance" for p in result)

        rows = db.query(BehaviouralPattern).filter_by(player_id=player.id).all()
        assert len(rows) >= 1
        qrow = next(r for r in rows if r.pattern_type == "queen_trade_avoidance")
        assert qrow.sample_count == 12
        assert qrow.confidence >= 0.5
        assert sorted(qrow.supporting_game_ids)  # populated
    finally:
        db.close()


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
