"""Tests for the scouting refutation finder (fake engine, no Stockfish)."""

from __future__ import annotations

import os

import chess
import pytest

os.environ.setdefault("APP_ENV", "dev")

from backend.services.opponent_scout import build_tree, parse_game  # noqa: E402
from backend.services.scout_refutations import find_refutations  # noqa: E402
from stockfish_engine import EngineUnavailableError  # noqa: E402
from tests.test_opponent_scout import _raw  # noqa: E402

BLACK_LINE = ["e4", "c6", "d4", "d5", "exd5", "cxd5"]


def _trees(games_moves, color="black", results=None):
    raws = []
    for i, moves in enumerate(games_moves):
        res = (results or ["win"] * len(games_moves))[i]
        raws.append(_raw(moves, scouted_color=color, result=res, t=i))
    games = [g for g in (parse_game(r, "target") for r in raws) if g]
    return {"white": build_tree(games, "white"), "black": build_tree(games, "black")}


def _fen(*sans):
    b = chess.Board()
    for s in sans:
        b.push_san(s)
    return b.fen()


class Fake:
    """Evals keyed by FEN: {fen: (eval_side_to_move, move, pv)}. Records calls."""

    def __init__(self, table):
        self.table = table
        self.calls = []

    def __call__(self, board, multipv):
        self.calls.append(board.fen())
        entry = self.table.get(board.fen())
        if entry is None:
            return []
        ev, move, pv = entry
        return [{"move": move, "eval": ev, "pv": pv}]


def test_habitual_blunder_found_with_pov_and_severity():
    trees = _trees([BLACK_LINE] * 3, results=["win", "resigned", "win"])
    after_e4 = _fen("e4")
    after_c6 = _fen("e4", "c6")
    fake = Fake({
        after_e4: (30, "e5", ["e5"]),
        after_c6: (350, "d4", ["d4", "d5"]),
    })
    out = find_refutations(trees, fake)
    hit = next(e for e in out if e["their_move"] == "c6")
    assert hit["opponent_color"] == "black"
    assert hit["eval_best_cp"] == 30
    assert hit["eval_after_cp"] == -350
    assert hit["loss_cp"] == 380
    assert hit["severity"] == "blunder"
    assert hit["best_move"] == "e5"
    assert hit["punish_move"] == "d4"
    assert hit["punish_line"] == ["d4", "d5"]
    assert hit["fen"] == after_e4
    assert hit["fen_after"] == after_c6
    assert hit["path"] == ["e4"]
    assert hit["line"] == "1. e4"
    assert hit["node_games"] == 3 and hit["their_move_games"] == 3
    assert hit["their_share"] == 100.0
    assert hit["their_score_pct"] == pytest.approx(66.7, abs=0.1)


@pytest.mark.parametrize("loss, sev", [(70, "inaccuracy"), (150, "mistake"), (250, "blunder")])
def test_severity_bands(loss, sev):
    trees = _trees([BLACK_LINE] * 3)
    fake = Fake({
        _fen("e4"): (0, "e5", ["e5"]),
        _fen("e4", "c6"): (loss, "d4", ["d4"]),
    })
    out = find_refutations(trees, fake)
    assert [e["severity"] for e in out if e["their_move"] == "c6"] == [sev]


def test_best_move_not_flagged_and_single_call():
    trees = _trees([BLACK_LINE] * 3)
    fake = Fake({_fen("e4"): (0, "c6", ["c6"])})
    out = find_refutations(trees, fake, max_positions=1)
    assert out == []
    assert len(fake.calls) == 1


def test_share_below_min_share_ignored():
    games = [["e4", "c6"], ["e4", "e5"], ["e4", "e6"], ["e4", "d6"]]
    trees = _trees([g + ["d4", "d5"] for g in games])
    fake = Fake({})
    assert find_refutations(trees, fake, min_share=0.5) == []
    assert fake.calls == []


def test_only_scouted_side_positions_examined():
    trees = _trees([BLACK_LINE] * 3)
    fake = Fake({})
    find_refutations(trees, fake)
    allowed = {_fen("e4"), _fen("e4", "c6", "d4"), _fen("e4", "c6", "d4", "d5", "exd5")}
    assert fake.calls and set(fake.calls) <= allowed
    assert chess.STARTING_FEN not in fake.calls


def test_white_root_included():
    trees = _trees([["e4", "e5", "Nf3", "Nc6"]] * 3, color="white")
    fake = Fake({chess.STARTING_FEN: (20, "d4", ["d4"])})
    find_refutations(trees, fake)
    assert chess.STARTING_FEN in fake.calls


def test_mate_scores_clipped():
    trees = _trees([BLACK_LINE] * 3)
    fake = Fake({
        _fen("e4"): (50, "e5", ["e5"]),
        _fen("e4", "c6"): (100000, "Qh5", ["Qh5"]),
    })
    hit = [e for e in find_refutations(trees, fake) if e["their_move"] == "c6"][0]
    assert hit["eval_after_cp"] == -10000
    assert hit["loss_cp"] == 10050


def test_still_winning_not_flagged_unless_big_loss():
    trees = _trees([BLACK_LINE] * 3)
    fake = Fake({
        _fen("e4"): (900, "e5", ["e5"]),
        _fen("e4", "c6"): (-500, "d4", ["d4"]),  # still +500, lost 400 -> flagged
    })
    assert [e for e in find_refutations(trees, fake) if e["their_move"] == "c6"]
    fake = Fake({
        _fen("e4"): (500, "e5", ["e5"]),
        _fen("e4", "c6"): (-400, "d4", ["d4"]),  # still +400, lost 100 -> not flagged
    })
    assert not [e for e in find_refutations(trees, fake) if e["their_move"] == "c6"]


def test_progress_and_missing_pv():
    trees = _trees([BLACK_LINE] * 3)
    ticks = []
    fake = Fake({
        _fen("e4"): (0, "e5", ["e5"]),
        _fen("e4", "c6"): (200, "d4", None),
    })
    out = find_refutations(trees, fake, progress=lambda d, t: ticks.append((d, t)))
    assert ticks and ticks[-1][0] == ticks[-1][1] == len(ticks)
    assert [e for e in out if e["their_move"] == "c6"][0]["punish_line"] == ["d4"]


def test_exception_for_one_position_does_not_kill_run():
    trees = _trees([BLACK_LINE] * 3)
    boom = _fen("e4", "c6", "d4", "d5", "exd5")
    inner = Fake({
        _fen("e4"): (0, "e5", ["e5"]),
        _fen("e4", "c6"): (300, "d4", ["d4"]),
    })

    def analyse(board, multipv):
        if board.fen() == boom:
            raise RuntimeError("engine hiccup")
        return inner(board, multipv)

    out = find_refutations(trees, analyse)
    assert any(e["their_move"] == "c6" for e in out)


def test_engine_unavailable_propagates():
    trees = _trees([BLACK_LINE] * 3)

    def analyse(board, multipv):
        raise EngineUnavailableError("no stockfish")

    with pytest.raises(EngineUnavailableError):
        find_refutations(trees, analyse)
