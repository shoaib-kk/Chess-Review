"""Unit tests for the Phase 2 feature extractor.

Each feature group is exercised with a small, hardcoded dataset of stand-in
position/game rows (plain objects with the same attributes the real ORM rows
expose). A final test runs the full orchestrator against a temporary SQLite DB.

Run with:  pytest player_model/tests/test_features.py
       or:  python -m player_model.tests.test_features
"""

from __future__ import annotations

import os
import tempfile

# Point the package at a throwaway SQLite DB *before* importing anything that
# reads config (only the orchestrator test actually touches it).
_TEST_DB = os.path.join(tempfile.gettempdir(), "pm_features_test.db")
for _suffix in ("", "-wal", "-shm"):
    try:
        os.remove(_TEST_DB + _suffix)
    except OSError:
        pass
os.environ["PM_DATABASE_URL"] = "sqlite:///" + _TEST_DB

import chess  # noqa: E402

from player_model import features as F  # noqa: E402

STARTING_FEN = chess.STARTING_FEN


# --------------------------------------------------------------------------- #
# Lightweight stand-ins for ORM rows
# --------------------------------------------------------------------------- #
class Pos:
    _id = 0

    def __init__(self, **kw):
        Pos._id += 1
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
    def __init__(self, id, result="1-0", color_played="white", pgn_raw="", time_control="600"):
        self.id = id
        self.result = result
        self.color_played = color_played
        self.pgn_raw = pgn_raw
        self.time_control = time_control


def approx(a, b, tol=1e-3):
    return a is not None and abs(a - b) <= tol


# --------------------------------------------------------------------------- #
# 1. Accuracy
# --------------------------------------------------------------------------- #
def _accuracy_dataset():
    cpls = [0, 5, 10, 15, 20, 25, 30, 100, 120, 250, 60, 40]
    positions = []
    for i, cpl in enumerate(cpls):
        positions.append(
            Pos(
                game_id=1 if i < 6 else 2,  # two games -> variance is defined
                cpl=cpl,
                is_mistake=(cpl == 120),
                is_blunder=(cpl == 250),
            )
        )
    return positions


def test_accuracy_features():
    positions = _accuracy_dataset()
    out = F.accuracy_features(positions, [Gm(1), Gm(2)])

    assert approx(out["mean_cpl"], 56.25)
    assert approx(out["median_cpl"], 27.5)
    assert out["cpl_std"] > 0
    assert approx(out["accuracy_score"], 5.7437, tol=0.05)
    assert approx(out["blunder_rate"], 0.8333)
    assert approx(out["mistake_rate"], 0.8333)
    assert approx(out["inaccuracy_rate"], 1.6667)
    assert out["accuracy_variance_across_games"] is not None
    assert out["accuracy_variance_across_games"] > 0


def test_accuracy_degrades_with_small_sample():
    out = F.accuracy_features([Pos(cpl=10) for _ in range(5)], [Gm(1)])
    assert out["mean_cpl"] is None
    assert out["accuracy_score"] is None
    assert out["blunder_rate"] is None


# --------------------------------------------------------------------------- #
# 2. Tactical
# --------------------------------------------------------------------------- #
QUEEN_CAP_FEN = "4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1"   # e4xd5 wins the queen
SAC_FEN = "4k3/8/8/4p3/8/8/3Q4/4K3 w - - 0 1"          # Qd4 hangs the queen to a pawn


def _tactical_dataset():
    cand = [50, 40, 10]  # all three within 50cp of the best -> complexity 3
    positions = [
        # found / missed tactical opportunity
        Pos(fen=QUEEN_CAP_FEN, move_played="e4d5", best_move="e4d5",
            eval_before=900, candidate_evals=cand),
        Pos(fen=QUEEN_CAP_FEN, move_played="e1e2", best_move="e4d5",
            eval_before=900, candidate_evals=cand),
        # two voluntary sacrifices (not blunders)
        Pos(fen=SAC_FEN, move_played="d2d4", eval_before=50, candidate_evals=cand),
        Pos(fen=SAC_FEN, move_played="d2d4", eval_before=50, candidate_evals=cand),
        # two brilliancies
        Pos(is_brilliant=True, candidate_evals=cand),
        Pos(is_brilliant=True, candidate_evals=cand),
    ]
    positions += [Pos(candidate_evals=cand) for _ in range(6)]  # padding -> 12 total
    return positions


def test_tactical_features():
    out = F.tactical_features(_tactical_dataset())
    assert approx(out["brilliant_move_rate"], 1.6667)
    assert approx(out["tactical_opportunity_conversion"], 0.5)   # 1 of 2 found
    assert approx(out["sacrifice_tendency"], 0.1667)             # 2 of 12
    assert approx(out["complexity_preference"], 3.0)


# --------------------------------------------------------------------------- #
# 3. Positional
# --------------------------------------------------------------------------- #
DOUBLED_FEN = "4k3/8/8/8/8/3P4/3P4/4K3 w - - 0 1"  # doubled, isolated, passed d-pawns


def test_positional_features():
    positions = [Pos(fen=DOUBLED_FEN) for _ in range(12)]
    out = F.positional_features(positions)

    assert out["pawn_structure_score"] == {
        "doubled_pawns": 1.0,
        "isolated_pawns": 2.0,
        "passed_pawns": 2.0,
    }
    assert approx(out["king_safety_index"], 35.0)
    assert approx(out["piece_activity_index"], 5.0)  # 4 king + 1 pawn move


def test_positional_degrades_with_small_sample():
    out = F.positional_features([Pos(fen=DOUBLED_FEN) for _ in range(4)])
    assert out["king_safety_index"] is None


# --------------------------------------------------------------------------- #
# 4. Endgame
# --------------------------------------------------------------------------- #
ENDGAME_FEN = "8/6k1/8/8/4P3/5PK1/8/8 w - - 0 40"  # K+2P vs K, White +2, White to move


def test_endgame_features():
    eg_positions = [Pos(game_id=1, ply=60 + i, fen=ENDGAME_FEN, cpl=20) for i in range(11)]
    middlegame = [Pos(game_id=2, ply=i, fen=STARTING_FEN, cpl=10) for i in range(3)]
    games = [Gm(1, result="1-0", color_played="white"),
             Gm(2, result="0-1", color_played="white")]

    out = F.endgame_features(eg_positions + middlegame, games)
    assert out["endgame_game_count"] == 1
    assert approx(out["endgame_accuracy"], 20.0)
    assert approx(out["endgame_conversion_rate"], 1.0)  # entered +2, won


# --------------------------------------------------------------------------- #
# 5. Style
# --------------------------------------------------------------------------- #
QUEEN_TRADE_FEN = "3qk3/8/8/8/8/8/3Q4/3K4 w - - 0 1"  # Qxd8 trades; Black Q is king-defended


def _style_dataset():
    positions = []
    positions += [Pos(fen=QUEEN_TRADE_FEN, move_played="d2d8", eval_before=100)
                  for _ in range(4)]   # initiate queen trade
    positions += [Pos(fen=QUEEN_TRADE_FEN, move_played="d1c1", eval_before=100)
                  for _ in range(2)]   # option exists, declined
    positions += [Pos(fen=STARTING_FEN, move_played="e2e4", eval_before=100)
                  for _ in range(6)]   # padding, no trade option
    return positions


def test_style_features():
    out = F.style_features(_style_dataset())
    assert approx(out["aggression_index"], 100.0)
    assert approx(out["trade_preference_by_piece"]["Q"], 0.6667)  # 4 of 6
    assert out["trade_preference_by_piece"]["R"] is None          # no rook trades offered
    assert approx(out["queen_trade_avoidance"], 0.3333)
    assert approx(out["initiative_index"], 0.3333)                # the 4 captures/checks


# --------------------------------------------------------------------------- #
# 6. Opening
# --------------------------------------------------------------------------- #
def _pgn(eco):
    return f'[Event "x"]\n[ECO "{eco}"]\n[Result "*"]\n\n1. e4 e5 *\n'


def test_opening_features():
    games = [Gm(1, pgn_raw=_pgn("C41")), Gm(2, pgn_raw=_pgn("C41")), Gm(3, pgn_raw=_pgn("B10"))]
    positions = [Pos(ply=2 * i, cpl=15) for i in range(1, 11)]  # 10 opening plies

    out = F.opening_features(positions, games)
    assert out["eco_distribution"] == {"C41": 2, "B10": 1}
    assert out["opening_repertoire_size"] == 2
    assert approx(out["opening_accuracy"], 15.0)
    assert approx(out["opening_flexibility"], 0.9183)  # entropy of {2/3, 1/3}


# --------------------------------------------------------------------------- #
# 7. Time
# --------------------------------------------------------------------------- #
def test_time_features_present():
    low = [Pos(clock_seconds=10, cpl=20, is_blunder=(i < 2)) for i in range(10)]
    high = [Pos(clock_seconds=120, cpl=5) for _ in range(2)]
    out = F.time_features(low + high)
    assert approx(out["time_pressure_cpl"], 20.0)
    assert approx(out["time_pressure_blunder_rate"], 2.0)  # 2 blunders / 10 * 10


def test_time_features_absent():
    out = F.time_features([Pos(clock_seconds=None) for _ in range(12)])
    assert out["time_pressure_cpl"] is None
    assert out["time_pressure_blunder_rate"] is None


# --------------------------------------------------------------------------- #
# Orchestrator (end-to-end against a temp SQLite DB)
# --------------------------------------------------------------------------- #
def test_compute_player_profile_orchestrator():
    from player_model.db import SessionLocal, init_db
    from player_model.features import compute_player_profile
    from player_model.models import Game, Player, PlayerProfile, Position

    init_db()
    db = SessionLocal()
    try:
        player = Player(username="orch_test_user")
        db.add(player)
        db.flush()

        game = Game(
            player_id=player.id,
            pgn_raw=_pgn("C41"),
            pgn_hash="hash-orch-1",
            color_played="white",
            result="1-0",
            time_control="600",
        )
        db.add(game)
        db.flush()

        for i in range(12):
            db.add(Position(
                game_id=game.id, ply=i + 1, fen=STARTING_FEN,
                move_played="e2e4", best_move="e2e4",
                eval_before=20, eval_after=20, cpl=10 + i,
            ))
        db.commit()

        features = compute_player_profile(player.id, db)
        assert set(features.keys()) == {
            "accuracy", "tactical", "positional", "endgame",
            "style", "opening", "time",
        }
        assert features["accuracy"]["mean_cpl"] is not None  # 12 samples >= MIN

        profile = db.get(PlayerProfile, player.id)
        assert profile is not None
        assert profile.game_count == 1
        assert profile.computed_at is not None
        assert profile.features["opening"]["eco_distribution"] == {"C41": 1}
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Direct runner (no pytest required)
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
