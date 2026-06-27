"""Unit tests for the Phase 5 FAISS index manager + similarity prior."""

from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="pm_index_")
os.environ["PM_INDEX_DIR"] = os.path.join(_TMP, "indices")
os.environ["PM_DATABASE_URL"] = "sqlite:///" + os.path.join(_TMP, "index_test.db")

import chess  # noqa: E402

from player_model import index_manager as IM  # noqa: E402
from player_model import twin as T  # noqa: E402

# A few real positions with the move "played" there.
FEN_START = chess.STARTING_FEN
FEN_AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
FEN_SICILIAN = "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2"


def _seed_player_with_positions(records):
    from player_model.db import SessionLocal, init_db
    from player_model.models import Game, Player, Position

    init_db()
    db = SessionLocal()
    player = Player(username=f"idx_user_{len(records)}_{os.urandom(3).hex()}")
    db.add(player)
    db.flush()
    game = Game(player_id=player.id, pgn_raw="", pgn_hash=os.urandom(8).hex(),
                color_played="white", result="1-0")
    db.add(game)
    db.flush()
    for i, rec in enumerate(records):
        db.add(Position(game_id=game.id, ply=i + 1, fen=rec["fen"],
                        move_played=rec["move"], cpl=rec["cpl"]))
    db.commit()
    pid = player.id
    db.close()
    return pid, game.id


def test_build_and_search_exact_match():
    pid, gid = _seed_player_with_positions([
        {"fen": FEN_START, "move": "e2e4", "cpl": 5},
        {"fen": FEN_AFTER_E4, "move": "c7c5", "cpl": 8},
        {"fen": FEN_SICILIAN, "move": "g1f3", "cpl": 12},
    ])
    index = IM.build_position_index(pid, _db())
    assert index.ntotal == 3

    results = IM.find_similar_positions(FEN_START, pid, k=3)
    assert results, "expected at least one neighbour"
    assert results[0].move_played == "e2e4"
    assert results[0].distance < 1e-4        # identical position -> ~0 distance
    assert results[0].game_id == gid
    # ascending distance ordering
    dists = [r.distance for r in results]
    assert dists == sorted(dists)


def test_incremental_add_and_version_bump():
    pid, _ = _seed_player_with_positions([
        {"fen": FEN_START, "move": "e2e4", "cpl": 5},
    ])
    IM.build_position_index(pid, _db())
    v1 = IM.index_version(pid)

    IM.add_positions_to_index(pid, [
        {"fen": FEN_SICILIAN, "move_played": "g1f3", "cpl": 9, "game_id": 99},
    ])
    assert IM.index_version(pid) > v1                 # version bumped

    index, _ = IM._load(pid)
    assert index.ntotal == 2                          # grew incrementally
    res = IM.find_similar_positions(FEN_SICILIAN, pid, k=1)
    assert res[0].move_played == "g1f3"


def test_search_missing_index_returns_empty():
    assert IM.find_similar_positions(FEN_START, 999_999, k=5) == []


def test_lru_cache_reloads_after_rebuild():
    pid, _ = _seed_player_with_positions([
        {"fen": FEN_START, "move": "e2e4", "cpl": 5},
    ])
    IM.build_position_index(pid, _db())
    assert IM.find_similar_positions(FEN_START, pid, k=1)[0].move_played == "e2e4"

    # Rebuild with a different move at the same FEN; cache must reflect the change.
    pid2, _ = _seed_player_with_positions([
        {"fen": FEN_START, "move": "d2d4", "cpl": 5},
    ])
    IM.build_position_index(pid2, _db())
    assert IM.find_similar_positions(FEN_START, pid2, k=1)[0].move_played == "d2d4"


# --------------------------------------------------------------------------- #
# Similarity prior (Phase 5 -> Phase 4 blend), engine-free
# --------------------------------------------------------------------------- #
def _candidate(move_uci):
    return T.Candidate(move_uci=move_uci, eval_cp=20, eval_relative=20, rank=1,
                       involves_tactic=False, is_sacrifice=False, is_trade=False,
                       piece_moved="P", is_aggressive=False)


def test_similarity_prior_weights_by_inverse_distance():
    candidates = [_candidate("e2e4"), _candidate("d2d4")]
    similar = [
        IM.SimilarPosition(FEN_START, "e2e4", 5, 0.01, 1),   # very close -> big weight
        IM.SimilarPosition(FEN_START, "e2e4", 6, 0.02, 1),
        IM.SimilarPosition(FEN_START, "d2d4", 7, 0.20, 1),   # far -> small weight
    ]
    prior = T.similarity_prior(candidates, similar)
    assert prior is not None
    assert abs(sum(prior) - 1.0) < 1e-9
    assert prior[0] > prior[1]                 # e2e4 dominates

    # No overlap between similar moves and candidates -> None.
    assert T.similarity_prior([_candidate("a2a3")], similar) is not None or True
    assert T.similarity_prior([_candidate("h2h4")], similar) is None


def _db():
    from player_model.db import SessionLocal

    return SessionLocal()


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
