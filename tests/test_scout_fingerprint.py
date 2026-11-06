"""Unit tests for the mistake fingerprint (fake evaluator, no engine, no network)."""

from __future__ import annotations

import os
import random

import chess
import chess.pgn

os.environ.setdefault("APP_ENV", "dev")

from backend.services.scout_fingerprint import build_fingerprint, classify_motif  # noqa: E402

ME = "Scouted"
FOE = "Other"
CARO = "https://www.chess.com/openings/Caro-Kann-Defense-Advance-Variation"


def rand_san_game(seed: int, plies: int) -> list[str]:
    rng = random.Random(seed)
    board = chess.Board()
    sans: list[str] = []
    while len(sans) < plies:
        move = rng.choice(list(board.legal_moves))
        sans.append(board.san(move))
        board.push(move)
        if board.is_game_over():
            return rand_san_game(seed + 1000, plies)
    return sans


def positions(sans: list[str]) -> list[chess.Board]:
    board = chess.Board()
    out = [board.copy()]
    for san in sans:
        board.push_san(san)
        out.append(board.copy())
    return out


def make_raw(sans, *, white=True, result="win", clocks=None, time_control="180+0", eco=CARO, end_time=1000):
    """Chess.com-style cleaned game dict. ``clocks`` = seconds left after each ply."""
    parts = []
    for i, san in enumerate(sans):
        prefix = f"{i // 2 + 1}. " if i % 2 == 0 else ""
        clk = ""
        if clocks is not None:
            c = clocks[i]
            clk = f" {{[%clk 0:{int(c // 60):02d}:{c % 60:04.1f}]}}"
        parts.append(f"{prefix}{san}{clk}")
    pgn = f'[Event "t"]\n[White "{ME if white else FOE}"]\n[Black "{FOE if white else ME}"]\n[ECOUrl "{eco}"]\n\n' + " ".join(parts) + " *\n"
    mine, theirs = {"win": ("win", "resigned"), "loss": ("resigned", "win"), "draw": ("agreed", "agreed")}[result]
    return {
        "white_username": ME if white else FOE,
        "black_username": FOE if white else ME,
        "white_result": mine if white else theirs,
        "black_result": theirs if white else mine,
        "end_time": end_time, "time_class": "blitz", "time_control": time_control,
        "rules": "chess", "url": f"https://chess.com/game/{end_time}", "pgn": pgn,
    }


def fake_eval(by_index: dict[tuple[tuple[str, ...], int], int]):
    """Flat 0 evaluator with per-(game, position index) overrides (side-to-move POV)."""
    table: dict[str, int] = {}
    for (sans_key, idx), value in by_index.items():
        table[positions(list(sans_key))[idx].epd()] = value
    calls = {"n": 0}

    def evaluate(board: chess.Board):
        calls["n"] += 1
        return table.get(board.epd(), 0), None, []

    evaluate.calls = calls  # type: ignore[attr-defined]
    return evaluate


def key(sans):
    return tuple(sans)


# ── basics ────────────────────────────────────────────────────────────────────


def test_returns_none_without_analysable_games():
    ev = fake_eval({})
    assert build_fingerprint([], ME, ev, depth=8) is None
    short = make_raw(rand_san_game(1, 10))
    assert build_fingerprint([short], ME, ev, depth=8) is None  # < 20 plies
    other = make_raw(rand_san_game(1, 30))
    assert build_fingerprint([other], "Nobody", ev, depth=8) is None
    daily = {**make_raw(rand_san_game(1, 30)), "rules": "chess960"}
    assert build_fingerprint([daily], ME, ev, depth=8) is None


def test_cp_loss_sign_and_pov_for_white_and_black():
    sans = rand_san_game(2, 20)
    # Black moves at ply 7: E7 = 0 (black to move), E8 = +300 (white to move) -> black loses 300.
    # Chain E9 = -300 keeps white's ply-8 move at 0 loss.
    black_ev = fake_eval({(key(sans), 8): 300, (key(sans), 9): -300})
    fp = build_fingerprint([make_raw(sans, white=False)], ME, black_ev, depth=8)
    assert fp["moves_analyzed"] == 10  # only black's moves are graded
    # losses: ply 7 -> 300 (E7=0,E8=300); ply 9 -> max(0,-300+0)=0; white moves never graded
    assert fp["avg_cp_loss"] == 30.0
    assert sum(p["blunders"] for p in fp["phases"]) == 1

    # Same overrides, scouted player White: ply 8 is theirs: E8=300 + E9=-300 = 0 loss
    fp_w = build_fingerprint([make_raw(sans, white=True)], ME, black_ev, depth=8)
    assert fp_w["moves_analyzed"] == 10
    assert fp_w["avg_cp_loss"] == 0.0

    # White blunder at ply 6: E6 = 0, E7 = +250 (black to move, black better)
    white_ev = fake_eval({(key(sans), 7): 250})
    fp_w2 = build_fingerprint([make_raw(sans, white=True)], ME, white_ev, depth=8)
    assert fp_w2["avg_cp_loss"] == 25.0
    assert fp_w2["worst_mistakes"][0]["move_number"] == 4
    assert fp_w2["worst_mistakes"][0]["color"] == "white"


def test_mate_is_clipped_and_loss_capped():
    sans = rand_san_game(3, 20)
    ev = fake_eval({(key(sans), 8): 100000})  # after black's ply-7 move white has a forced mate
    fp = build_fingerprint([make_raw(sans, white=False)], ME, ev, depth=8)
    worst = fp["worst_mistakes"][0]
    assert worst["cp_loss"] == 1000
    assert worst["motif"] == "allowed_mate"
    assert fp["avg_cp_loss"] == 100.0  # 1000 / 10 moves

    # missed mate: black had mate (E7 = +100000) and then no longer does (E8 = 0)
    ev2 = fake_eval({(key(sans), 7): 100000})
    fp2 = build_fingerprint([make_raw(sans, white=False)], ME, ev2, depth=8)
    assert fp2["worst_mistakes"][0]["motif"] == "missed_mate"


def test_phases_split_opening_and_later():
    sans = rand_san_game(4, 60)
    fp = build_fingerprint([make_raw(sans)], ME, fake_eval({}), depth=8)
    by = {p["phase"]: p for p in fp["phases"]}
    assert by["opening"]["moves"] == 12
    assert by["middlegame"]["moves"] + by["endgame"]["moves"] == 18
    assert fp["accuracy_estimate"] == 100.0
    assert fp["depth"] == 8


# ── motifs ────────────────────────────────────────────────────────────────────


def test_hanging_piece_blunder_classified():
    board = chess.Board("4k3/8/3p4/8/8/5N2/8/4K3 w - - 0 1")
    move = chess.Move.from_uci("f3e5")  # knight lands on a square the d6 pawn guards
    assert classify_motif(board, move, 0, 300, None, "dxe5", []) == "hanging_piece"


def test_fork_classified():
    board = chess.Board("4k3/8/8/4n3/8/8/P2R4/6K1 w - - 0 1")
    move = chess.Move.from_uci("a2a3")  # irrelevant move; Nf3+ forks king and rook
    assert classify_motif(board, move, 0, 400, None, "Nf3+", []) == "fork"


def test_missed_capture_and_other():
    board = chess.Board("4k3/8/8/3q4/8/8/8/3RK3 w - - 0 1")
    quiet = chess.Move.from_uci("e1f1")
    assert classify_motif(board, quiet, 0, 900, "Rxd5", None, []) == "missed_capture"
    assert classify_motif(board, quiet, 0, 150, None, None, []) == "other"


def test_pin_classified():
    board = chess.Board("4r1k1/8/8/8/8/8/4N3/4K3 w - - 0 1")  # Ne2 already pinned on e-file
    move = chess.Move.from_uci("e1d1")
    # king leaves the file: not a pin afterwards
    assert classify_motif(board, move, 0, 200, None, None, []) != "pin"
    board2 = chess.Board("4r1k1/8/8/8/8/8/3N4/4K3 w - - 0 1")
    move2 = chess.Move.from_uci("d2e4")  # knight steps onto the e-file: absolutely pinned to Ke1
    assert classify_motif(board2, move2, 0, 200, "Kd2", "Kf8", []) == "pin"


# ── time pressure, conversion, cliffs, progress ──────────────────────────────


def test_time_pressure_buckets_from_clocks():
    sans = rand_san_game(5, 20)
    white_left = [170, 140, 100, 80, 60, 40, 30, 20, 10, 5]  # 94,78,56,44,33,22,17,11,5.6,2.8 %
    clocks = []
    for i in range(20):
        clocks.append(white_left[i // 2] if i % 2 == 0 else 100)
    fp = build_fingerprint([make_raw(sans, clocks=clocks)], ME, fake_eval({}), depth=8)
    counts = {b["key"]: b["moves"] for b in fp["time_pressure"]["buckets"]}
    assert counts == {"plenty": 3, "comfortable": 3, "low": 2, "scramble": 2}

    daily = make_raw(sans, time_control="1/259200", clocks=clocks)
    fp2 = build_fingerprint([daily], ME, fake_eval({}), depth=8)
    assert all(b["moves"] == 0 for b in fp2["time_pressure"]["buckets"])
    assert fp2["moves_analyzed"] == 10


def test_conversion_counts():
    games = []
    overrides = {}
    for seed, (idx, value, result) in enumerate([
        (24, 300, "win"),    # winning, converted
        (24, 300, "loss"),   # winning, thrown away
        (26, -300, "draw"),  # losing, saved
        (26, -300, "loss"),  # losing, lost
        (10, 300, "loss"),   # early eval (before move 10) must not count
    ]):
        sans = rand_san_game(100 + seed, 40)
        overrides[(key(sans), idx)] = value
        games.append(make_raw(sans, result=result, end_time=1000 + seed))
    fp = build_fingerprint(games, ME, fake_eval(overrides), depth=8)
    c = fp["conversion"]
    assert (c["winning_games"], c["converted"], c["converted_pct"]) == (2, 1, 50.0)
    assert (c["losing_games"], c["saved"], c["saved_pct"]) == (2, 1, 50.0)


def test_opening_cliff_detection():
    games = []
    overrides = {}
    for seed in range(3):
        sans = rand_san_game(200 + seed, 40)
        for m in range(6, 21):  # white loses 100cp on moves 6..20: E_{2(m-1)+1} = 100
            overrides[(key(sans), 2 * (m - 1) + 1)] = 100
        games.append(make_raw(sans, end_time=2000 + seed))
    fp = build_fingerprint(games, ME, fake_eval(overrides), depth=8)
    assert len(fp["opening_cliffs"]) == 1
    cliff = fp["opening_cliffs"][0]
    assert (cliff["color"], cliff["games"]) == ("white", 3)
    assert cliff["cliff_move"] == 5  # mean(5,6,7)=66.7 >= 40 and >= 2x the zero before it
    assert cliff["avg_cp_loss_before"] == 0.0
    assert all(row["samples"] == 3 for row in cliff["by_move"])
    assert any("drops off" in line for line in fp["insights"])

    # two games only -> no cliff entry
    fp2 = build_fingerprint(games[:2], ME, fake_eval(overrides), depth=8)
    assert fp2["opening_cliffs"] == []


def test_progress_callback_and_eval_cache():
    sans = rand_san_game(7, 24)
    ev = fake_eval({})
    seen: list[tuple[int, int]] = []
    fp = build_fingerprint([make_raw(sans)], ME, ev, depth=8, progress=lambda d, t: seen.append((d, t)))
    assert fp is not None
    assert seen[0] == (1, 25) and seen[-1] == (25, 25)
    assert [d for d, _ in seen] == list(range(1, 26))
    assert ev.calls["n"] <= 25  # type: ignore[attr-defined]

    # the same game twice is served from the cache
    ev2 = fake_eval({})
    build_fingerprint([make_raw(sans, end_time=1), make_raw(sans, end_time=2)], ME, ev2, depth=8)
    assert ev2.calls["n"] <= 25  # type: ignore[attr-defined]


def test_max_games_and_max_plies():
    games = [make_raw(rand_san_game(300 + i, 30), end_time=i) for i in range(5)]
    seen: list[tuple[int, int]] = []
    fp = build_fingerprint(games, ME, fake_eval({}), depth=8, max_games=2, max_plies=20, progress=lambda d, t: seen.append((d, t)))
    assert fp["games_analyzed"] == 2
    assert seen[-1] == (42, 42)  # 2 games x 21 positions
