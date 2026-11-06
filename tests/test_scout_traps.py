"""Unit tests for trap finding and the Lichess explorer client (no network)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("APP_ENV", "dev")

import chess  # noqa: E402

from backend.services import lichess_explorer as lx  # noqa: E402
from backend.services.lichess_explorer import LichessExplorerError  # noqa: E402
from backend.services.opponent_scout import build_tree, parse_game  # noqa: E402
from backend.services.scout_traps import (  # noqa: E402
    find_trappy_lines,
    lichess_rating_buckets,
    lichess_speeds,
    rating_band_label,
)


def _raw(moves, *, color, t=0):
    parts = []
    for i, san in enumerate(moves):
        parts.append((f"{i // 2 + 1}. " if i % 2 == 0 else "") + san)
    scouted, foe = "target", "foe"
    white, black = (scouted, foe) if color == "white" else (foe, scouted)
    pgn = (f'[Event "x"]\n[White "{white}"]\n[Black "{black}"]\n[Result "*"]\n'
           f'[WhiteElo "1500"]\n[BlackElo "1500"]\n[TimeControl "180"]\n\n' + " ".join(parts) + " *")
    return {
        "white_username": white, "black_username": black,
        "white_result": "win", "black_result": "resigned", "end_time": 1_700_000_000 + t,
        "date": "2026-10-01", "time_class": "blitz", "time_control": "180", "rated": True,
        "rules": "chess", "url": f"u{t}", "pgn": pgn,
    }


def _trees(specs):
    games = [parse_game(_raw(m, color=c, t=i), "target") for i, (c, m) in enumerate(specs)]
    return {"white": build_tree(games, "white"), "black": build_tree(games, "black")}


def _entry(san, white, draws, black):
    return {"san": san, "white": white, "draws": draws, "black": black}


def _resp(moves):
    return {
        "white": sum(m["white"] for m in moves), "draws": sum(m["draws"] for m in moves),
        "black": sum(m["black"] for m in moves), "moves": moves,
    }


# Black to move after 1.e4: trap c5? Build for black: c6 scores 30%, e5 scores 55% (black POV).
BLACK_TRAP = _resp([
    _entry("c6", 60, 20, 20),     # 100 games, black scores (20+10)/100 = 30%
    _entry("e5", 20, 10, 70),     # 100 games, black scores 75%
])
BLACK_SPECS = [("black", ["e4", "c6", "d4", "d5"])] * 3


def test_detects_trap_scored_for_black():
    trees = _trees(BLACK_SPECS)
    out = find_trappy_lines(trees, lambda fen: BLACK_TRAP, rating_band="1400-1800", speeds=["blitz"])
    first = [o for o in out if o["path"] == ["e4"]][0]
    assert first["trap_move"] == "c6"
    assert first["trap_score_pct"] == 30.0
    assert first["trap_share"] == 50.0
    assert first["best_move"] == "e5" and first["best_score_pct"] == 75.0
    assert first["lichess_games"] == 200
    assert first["rating_band"] == "1400-1800" and first["speeds"] == ["blitz"]
    assert first["their_games_here"] == 3
    assert first["their_moves_here"] == [{"san": "c6", "games": 3}]
    assert first["line"] == "1. e4"
    assert "They have played c6" in first["reason"]


def test_score_uses_correct_side_for_white():
    # White to move after 1.e4 e5: Nf3 is a trap only if white's score is low.
    resp = _resp([_entry("Bc4", 20, 10, 70), _entry("Nf3", 70, 10, 20)])
    trees = _trees([("white", ["e4", "e5", "Nf3"])] * 2)
    out = find_trappy_lines(trees, lambda fen: resp, rating_band="b", speeds=["blitz"])
    assert [o["trap_move"] for o in out] == ["Bc4"]
    assert out[0]["trap_score_pct"] == 25.0
    assert out[0]["best_move"] == "Nf3"
    # the same numbers read for black would flip it
    flipped = find_trappy_lines(_trees(BLACK_SPECS), lambda fen: _resp([_entry("c6", 20, 10, 70), _entry("e5", 70, 10, 20)]),
                                rating_band="b", speeds=["blitz"])
    assert {o["trap_move"] for o in flipped} == {"e5"}


@pytest.mark.parametrize("trap_move, expect", [
    (_entry("c6", 60, 20, 20), True),
    (_entry("c6", 40, 20, 40), False),      # scores 50% -> not bad enough
    (_entry("c6", 55, 10, 35), True),       # 40% boundary is inclusive
])
def test_score_threshold(trap_move, expect):
    resp = _resp([trap_move, _entry("e5", 20, 10, 70)])
    out = find_trappy_lines(_trees(BLACK_SPECS), lambda fen: resp, rating_band="b", speeds=["blitz"])
    assert bool(out) is expect


def test_share_and_volume_thresholds():
    best = _entry("e5", 20, 10, 70)
    # share below 12%
    small_share = _resp([_entry("c6", 12, 2, 4), best, _entry("d5", 300, 100, 300)])
    assert find_trappy_lines(_trees(BLACK_SPECS), lambda f: small_share, rating_band="b", speeds=[]) == []
    # fewer than 50 games though high share
    few = _resp([_entry("c6", 30, 10, 9), best])
    few["moves"][1] = _entry("e5", 0, 0, 0)
    assert find_trappy_lines(_trees(BLACK_SPECS), lambda f: few, rating_band="b", speeds=[]) == []
    # no good alternative (best < 30 games or < 50%)
    no_best = _resp([_entry("c6", 60, 20, 20), _entry("e5", 10, 5, 10)])
    assert find_trappy_lines(_trees(BLACK_SPECS), lambda f: no_best, rating_band="b", speeds=[]) == []
    poor_best = _resp([_entry("c6", 60, 20, 20), _entry("e5", 60, 10, 30)])
    assert find_trappy_lines(_trees(BLACK_SPECS), lambda f: poor_best, rating_band="b", speeds=[]) == []


def test_only_positions_where_scouted_player_is_to_move_are_fetched():
    trees = _trees([("black", ["e4", "c6", "d4", "d5"])] * 3 + [("white", ["e4", "e5", "Nf3", "Nc6"])] * 3)
    seen = []

    def fetch(fen):
        seen.append(fen)
        return {"white": 0, "draws": 0, "black": 0, "moves": []}

    find_trappy_lines(trees, fetch, rating_band="b", speeds=[])
    for fen in seen:
        board = chess.Board(fen)
        # Scouted player is black in the black tree (black to move) and white in the white tree.
        assert fen  # sanity
    plies_black_to_move = {chess.Board(f).turn for f in seen}
    assert plies_black_to_move == {chess.WHITE, chess.BLACK}
    # 1.e4 / 1.e4 c6 2.d4 (black tree, black to move) and 1.e4 e5 / 1.e4 e5 2.Nf3 Nc6 (white tree, white to move): 4 positions
    assert len(seen) == 4
    assert len(set(seen)) == 4


def test_unplayed_trap_and_ranking_prefers_played():
    # Two positions both trappy; the one whose trap move they played ranks first despite smaller size.
    trees = _trees([("black", ["e4", "c6", "d4", "d5"])] * 3 + [("black", ["d4", "Nf6", "c4", "e6"])] * 2)

    def fetch(fen):
        board = chess.Board(fen)
        if board.fullmove_number == 1 and board.piece_at(chess.E4):
            return BLACK_TRAP                                 # they played c6 (the trap)
        return _resp([_entry("Nf6", 200, 100, 100), _entry("d5", 20, 10, 70)])  # trap Nf6? black scores 30%; they play Nf6

    out = find_trappy_lines(trees, fetch, rating_band="b", speeds=[])
    assert len(out) >= 2
    assert all("They have played" in o["reason"] for o in out[:2])
    unplayed = _resp([_entry("e5", 20, 10, 70), _entry("c5", 60, 20, 20)])
    out2 = find_trappy_lines(_trees(BLACK_SPECS), lambda f: unplayed, rating_band="b", speeds=[])
    assert out2 and "They have played" not in out2[0]["reason"]


def test_graceful_stop_after_partial_results():
    trees = _trees(BLACK_SPECS)
    calls = []

    def fetch(fen):
        calls.append(fen)
        if len(calls) == 1:
            return BLACK_TRAP
        raise LichessExplorerError("boom")

    out = find_trappy_lines(trees, fetch, rating_band="b", speeds=[])
    assert len(calls) == 2 and len(out) == 1


def test_first_failure_is_reraised():
    def fetch(fen):
        raise LichessExplorerError("no token")

    with pytest.raises(LichessExplorerError):
        find_trappy_lines(_trees(BLACK_SPECS), fetch, rating_band="b", speeds=[])


def test_max_positions_and_progress():
    trees = _trees(BLACK_SPECS)
    ticks = []
    calls = []
    find_trappy_lines(trees, lambda f: calls.append(f) or {}, rating_band="b", speeds=[], max_positions=1,
                      progress=lambda d, t: ticks.append((d, t)))
    assert len(calls) == 1 and ticks == [(1, 1)]


def test_rating_buckets_and_speeds():
    assert lichess_rating_buckets(1200, "blitz") == [1400, 1600]    # est 1450
    assert lichess_rating_buckets(1500, "blitz") == [1600, 1800]    # est 1750
    assert lichess_rating_buckets(None, "blitz") == [1400, 1600]
    assert lichess_rating_buckets(100, "rapid") == [0, 1000]
    assert lichess_rating_buckets(3000, "blitz") == [2200, 2500]
    assert lichess_speeds("bullet") == ["bullet"]
    assert lichess_speeds("daily") == ["correspondence", "classical"]
    assert lichess_speeds(None) == ["blitz", "rapid"]
    assert rating_band_label([1400, 1600]) == "1400-1800"


# ── explorer client ──────────────────────────────────────────────────────────


class FakeResponse:
    def __init__(self, status=200, payload=None, bad_json=False):
        self.status_code = status
        self._payload = payload if payload is not None else {"white": 1, "draws": 0, "black": 0, "moves": []}
        self._bad = bad_json

    def json(self):
        if self._bad:
            raise ValueError("bad")
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params, headers, timeout))
        return self.responses.pop(0)


@pytest.fixture
def client(monkeypatch):
    clock = {"t": 1000.0}
    sleeps = []

    def fake_sleep(s):
        sleeps.append(s)
        clock["t"] += s

    monkeypatch.setattr(lx, "_sleep", fake_sleep)
    monkeypatch.setattr(lx, "_now", lambda: clock["t"])
    monkeypatch.setattr(lx, "_last_request", 0.0)
    monkeypatch.setenv("LICHESS_TOKEN", "tok")
    lx._fetch_cached.cache_clear()

    def install(responses):
        session = FakeSession(responses)
        monkeypatch.setattr(lx, "_SESSION", session)
        return session

    yield install, sleeps
    lx._fetch_cached.cache_clear()


def test_missing_token_raises_without_network(client, monkeypatch):
    install, _ = client
    session = install([])
    monkeypatch.delenv("LICHESS_TOKEN")
    with pytest.raises(LichessExplorerError, match="LICHESS_TOKEN"):
        lx.fetch_explorer("fen", ratings=[1400], speeds=["blitz"])
    assert session.calls == []


def test_request_shape_caching_and_key(client):
    install, _ = client
    session = install([FakeResponse(), FakeResponse()])
    lx.fetch_explorer("fen1", ratings=[1600, 1400], speeds=["blitz"])
    lx.fetch_explorer("fen1", ratings=[1400, 1600], speeds=["blitz"])   # cached (order-insensitive)
    assert len(session.calls) == 1
    url, params, headers, timeout = session.calls[0]
    assert url.endswith("/lichess") and params["ratings"] == "1400,1600" and params["speeds"] == "blitz"
    assert headers["Authorization"] == "Bearer tok" and timeout == (5, 15)
    lx.fetch_explorer("fen1", ratings=[1400, 1600], speeds=["rapid"])   # different key
    assert len(session.calls) == 2


def test_throttle_spaces_requests(client):
    install, sleeps = client
    install([FakeResponse(), FakeResponse()])
    lx.fetch_explorer("a", ratings=[1400], speeds=["blitz"])
    lx.fetch_explorer("b", ratings=[1400], speeds=["blitz"])
    assert sleeps and sleeps[-1] == pytest.approx(1.0)


def test_429_waits_once_then_succeeds_or_raises(client):
    install, sleeps = client
    session = install([FakeResponse(429), FakeResponse()])
    assert lx.fetch_explorer("x", ratings=[1400], speeds=["blitz"])["white"] == 1
    assert 60.0 in sleeps and len(session.calls) == 2

    install([FakeResponse(429), FakeResponse(429)])
    with pytest.raises(LichessExplorerError, match="rate limiting"):
        lx.fetch_explorer("y", ratings=[1400], speeds=["blitz"])


@pytest.mark.parametrize("response, message", [
    (FakeResponse(401), "token"),
    (FakeResponse(500), "HTTP 500"),
    (FakeResponse(bad_json=True), "malformed"),
])
def test_http_and_json_errors(client, response, message):
    install, _ = client
    install([response])
    with pytest.raises(LichessExplorerError, match=message):
        lx.fetch_explorer("z", ratings=[1400], speeds=["blitz"])
