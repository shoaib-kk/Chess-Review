"""Unit tests for the pure opponent-scouting logic (no network, no engine)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("APP_ENV", "dev")

from backend.services.opponent_scout import (  # noqa: E402
    build_scouting_report,
    expected_score,
    opening_from_eco_url,
    parse_game,
    parse_time_control,
    shrunk_delta,
    split_opening,
)

CARO_EXCHANGE = ["e4", "c6", "d4", "d5", "exd5", "cxd5", "Bd3", "Nc6", "c3", "Nf6", "Bf4", "Bg4", "Qb3", "Qd7"]
QGD = ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7", "e3", "O-O", "Nf3", "h6", "Bh4", "b6"]
ITALIAN = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", "Nf6", "d3", "d6", "O-O", "O-O", "Re1", "a6"]
SICILIAN = ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6", "Be3", "e5", "Nb3", "Be6"]


def _pgn(moves: list[str], *, white: str, black: str, eco_url: str, white_elo=1500, black_elo=1500,
         base=180, inc=0, slow_ply: int | None = None) -> str:
    """Build a Chess.com-style PGN with [%clk] comments. Each own move costs 2s;
    ``slow_ply`` (0-based) costs 60s instead."""
    clocks = {"w": float(base), "b": float(base)}
    parts = []
    for i, san in enumerate(moves):
        side = "w" if i % 2 == 0 else "b"
        clocks[side] -= 60 if i == slow_ply else 2
        clocks[side] += inc
        c = clocks[side]
        clk = f"{int(c // 3600)}:{int(c % 3600 // 60):02d}:{c % 60:04.1f}"
        prefix = f"{i // 2 + 1}. " if side == "w" else f"{i // 2 + 1}... "
        parts.append(f"{prefix}{san} {{[%clk {clk}]}}")
    headers = (
        f'[Event "Live Chess"]\n[White "{white}"]\n[Black "{black}"]\n[Result "*"]\n'
        f'[ECOUrl "{eco_url}"]\n[WhiteElo "{white_elo}"]\n[BlackElo "{black_elo}"]\n'
        f'[TimeControl "{base}+{inc}"]\n\n'
    )
    return headers + " ".join(parts) + " *"


def _raw(moves, *, scouted="target", scouted_color="black", result="win", eco="Caro-Kann-Defense-Exchange-Variation",
         t=0, foe="foe", elo=(1500, 1500), slow_ply=None, foe_result=None):
    white, black = (scouted, foe) if scouted_color == "white" else (foe, scouted)
    other = {"win": "resigned", "resigned": "win", "timeout": "win", "checkmated": "win", "agreed": "agreed"}[result]
    own_res, foe_res = result, foe_result or other
    white_res, black_res = (own_res, foe_res) if scouted_color == "white" else (foe_res, own_res)
    return {
        "white_username": white,
        "black_username": black,
        "white_result": white_res,
        "black_result": black_res,
        "white_accuracy": None,
        "black_accuracy": None,
        "end_time": 1_700_000_000 + t,
        "date": "2026-10-01",
        "time_class": "blitz",
        "time_control": "180",
        "rated": True,
        "rules": "chess",
        "url": f"https://www.chess.com/game/live/{t}",
        "pgn": _pgn(moves, white=white, black=black, eco_url=f"https://www.chess.com/openings/{eco}",
                    white_elo=elo[0], black_elo=elo[1], slow_ply=slow_ply),
    }


# ── naming ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url, family, variation",
    [
        ("https://www.chess.com/openings/Caro-Kann-Defense-Advance-Variation-3...Bf5", "Caro-Kann Defense", "Advance Variation"),
        ("https://www.chess.com/openings/Kings-Indian-Defense-Fianchetto-Variation-8.d5-Nb8", "King's Indian Defense", "Fianchetto Variation"),
        ("https://www.chess.com/openings/Sicilian-Defense-Najdorf-Variation-English-Attack-6...e5", "Sicilian Defense", "Najdorf Variation"),
        ("https://www.chess.com/openings/Kings-Pawn-Opening", "King's Pawn Game", None),
        ("https://www.chess.com/openings/Indian-Game-Knights-Variation", "Indian Game", "Knights Variation"),
    ],
)
def test_opening_name_from_chesscom_slug(url, family, variation):
    assert split_opening(opening_from_eco_url(url)) == (family, variation)


def test_time_control_parsing():
    assert parse_time_control("180+2") == (180.0, 2.0)
    assert parse_time_control("600") == (600.0, 0.0)
    assert parse_time_control("1/259200") == (None, 0.0)  # daily: no clock analysis


def test_expected_score_and_shrinkage():
    assert expected_score(1500, 1500) == pytest.approx(0.5)
    assert expected_score(1900, 1500) == pytest.approx(1 - expected_score(1500, 1900))
    assert expected_score(None, 1500) is None
    # One lucky game barely moves the needle; many games do.
    assert abs(shrunk_delta(1, 0.5, 1)) < abs(shrunk_delta(20, 10, 20))
    assert shrunk_delta(0, 0, 0) == 0.0


# ── per-game parsing ──────────────────────────────────────────────────────────


def test_parse_game_pov_result_and_clock():
    raw = _raw(CARO_EXCHANGE, result="timeout", slow_ply=7)  # their 4th move (ply 7) is a long think
    game = parse_game(raw, "TARGET")  # username match is case-insensitive
    assert game is not None
    assert game.color == "black"
    assert game.score == 0
    assert game.result_reason == "loss:time"
    assert game.family == "Caro-Kann Defense"
    assert game.sans[:2] == ["e4", "c6"]
    assert game.first_long_think == 4
    # Seven own moves: six at 2s plus one 60s think, out of a 180s base.
    assert game.opening_time_pct == pytest.approx((6 * 2 + 60) / 180 * 100, abs=0.1)
    assert game.fen_at_eval is None  # game shorter than the eval ply


def test_parse_game_ignores_other_players_and_variants():
    assert parse_game(_raw(CARO_EXCHANGE), "someone-else") is None
    variant = _raw(CARO_EXCHANGE)
    variant["rules"] = "chess960"
    assert parse_game(variant, "target") is None


# ── report ────────────────────────────────────────────────────────────────────


def _opponent_games():
    games = []
    t = 0
    # As Black: collapses against 1.e4 (Caro-Kann Exchange) despite being higher rated…
    for _ in range(6):
        t += 1
        games.append(_raw(CARO_EXCHANGE, result="resigned", t=t, elo=(1400, 1600), slow_ply=9))
    # …but is solid against 1.d4.
    for _ in range(6):
        t += 1
        games.append(_raw(QGD, result="win", t=t, eco="Queens-Gambit-Declined-Orthodox-Defense"))
    # As White: plays 1.e4, crushes 1...e5, struggles with the Sicilian.
    for _ in range(5):
        t += 1
        games.append(_raw(ITALIAN, scouted_color="white", result="win", t=t, eco="Italian-Game-Giuoco-Pianissimo"))
    for _ in range(4):
        t += 1
        games.append(_raw(SICILIAN, scouted_color="white", result="checkmated", t=t, eco="Sicilian-Defense-Najdorf-Variation"))
    return games


def test_report_finds_weakness_and_strength():
    report = build_scouting_report("target", _opponent_games())

    prof = report["profile"]
    assert prof["games"] == 21
    assert prof["black"]["games"] == 12 and prof["white"]["games"] == 9

    vs = {row["move"]: row for row in report["as_black"]["vs_first_moves"]}
    assert vs["e4"]["score_pct"] == 0 and vs["d4"]["score_pct"] == 100
    assert vs["e4"]["expected_pct"] > 50  # they were the higher-rated side
    assert vs["e4"]["shrunk_delta"] < 0 < vs["d4"]["shrunk_delta"]

    replies = {r["move"]: r for r in report["as_white"]["first_moves"][0]["replies"]}
    assert replies["c5"]["score_pct"] == 0 and replies["e5"]["score_pct"] == 100

    # The plan tells you to open 1.e4 and answer their 1.e4 with the Sicilian.
    assert any("1.e4" in line and line.startswith("Open") for line in report["game_plan"]["you_white"])
    assert any("1.e4 c5" in line for line in report["game_plan"]["you_black"])

    # Steer points are positions after *your* move, never theirs.
    steer_paths = [tuple(e["path"]) for e in report["steer_into"]]
    assert ("e4",) in steer_paths
    assert ("e4", "c5") in steer_paths
    for entry in report["steer_into"]:
        ply = len(entry["path"])
        your_move_was_white = ply % 2 == 1
        assert your_move_was_white == (entry["opponent_color"] == "black")
    assert any(e["path"] == ["d4"] for e in report["avoid"])


def test_familiarity_and_book_depth():
    report = build_scouting_report("target", _opponent_games())
    black = {row["family"]: row for row in report["families"]["black"]}
    caro = black["Caro-Kann Defense"]
    # Every game follows the same line, so their own moves are all "book".
    assert caro["avg_book_depth"] >= 6
    assert caro["main_line"].startswith("1. e4 c6 2. d4 d5")
    assert caro["familiarity"]["label"] in {"Main weapon", "Comfortable"}
    # Long think at ply 9 shows up as a slower opening than the QGD.
    assert caro["avg_opening_time_pct"] > black["Queen's Gambit Declined"]["avg_opening_time_pct"]
    assert caro["familiarity"]["components"]["speed"] < black["Queen's Gambit Declined"]["familiarity"]["components"]["speed"]


def test_tree_labels_movers_and_counts():
    tree = build_scouting_report("target", _opponent_games())["tree"]["black"]
    assert tree["games"] == 12
    e4 = next(c for c in tree["children"] if c["san"] == "e4")
    assert e4["by"] == "you" and e4["games"] == 6 and e4["frequency"] == 50.0
    c6 = e4["children"][0]
    assert c6["san"] == "c6" and c6["by"] == "them" and c6["path"] == ["e4", "c6"]


def test_engine_evaluator_hook_and_failure():
    def fake_eval(games):
        for g in games:
            g.eval_cp = -150 if g.family == "Caro-Kann Defense" else 30
        return {"available": True, "evaluated_games": len(games)}

    report = build_scouting_report("target", _opponent_games(), evaluator=fake_eval)
    assert report["engine"]["enabled"] and report["engine"]["available"]
    black = {row["family"]: row for row in report["families"]["black"]}
    assert black["Caro-Kann Defense"]["avg_eval_cp"] == -150

    def broken(_games):
        raise RuntimeError("engine gone")

    report = build_scouting_report("target", _opponent_games(), evaluator=broken)
    assert report["engine"]["available"] is False  # report still produced


def test_matchup_uses_my_games():
    mine = []
    for i in range(4):
        mine.append(_raw(CARO_EXCHANGE, scouted="me", scouted_color="white", result="win", t=100 + i))
    for i in range(3):
        mine.append(_raw(SICILIAN, scouted="me", scouted_color="black", result="win", t=200 + i))
    report = build_scouting_report("target", _opponent_games(), my_username="me", my_raw_games=mine)
    matchup = report["matchup"]
    assert matchup["username"] == "me"
    assert matchup["you_white"][0]["move"] == "e4"
    assert matchup["you_white"][0]["edge"] > 0
    vs_e4 = next(row for row in matchup["you_black"] if row["their_move"] == "e4")
    assert vs_e4["options"][0]["reply"] == "c5"


@pytest.mark.parametrize(
    "slug, family, variation",
    [
        ("Alapin-Sicilian-Defense...6.cxd4", "Sicilian Defense", "Alapin Variation"),
        ("Closed-Sicilian-Defense-Grand-Prix-Variation...5.Bb5-Bd7", "Sicilian Defense", "Grand Prix Variation"),
        ("Alekhines-Defense-Modern-Variation", "Alekhine Defense", "Modern Variation"),
        ("Caro-Kann-Defense...3.d3", "Caro-Kann Defense", None),
    ],
)
def test_opening_name_edge_cases(slug, family, variation):
    assert split_opening(opening_from_eco_url(f"https://www.chess.com/openings/{slug}")) == (family, variation)


def test_undefined_slug_falls_back():
    assert opening_from_eco_url("https://www.chess.com/openings/Undefined") is None
