"""Unit tests for the engine-free scout habit analysis (no network, no engine)."""

from __future__ import annotations

import os
from datetime import datetime, timezone

os.environ.setdefault("APP_ENV", "dev")

from backend.services.scout_habits import build_habits, build_head_to_head  # noqa: E402

T0 = 1_700_000_000

# 1. e4 e5 2. Qh5 Nf6 3. Qxe5+ Qe7 4. Qxe7+ Bxe7, then knights shuffle until move 32.
_QUEENLESS = ["e4", "e5", "Qh5", "Nf6", "Qxe5+", "Qe7", "Qxe7+", "Bxe7"] + ["Nc3", "Nc6", "Nb1", "Nb8"] * 14
OPPOSITE = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "O-O", "Nf6", "d3", "d6", "Nc3", "Bg4", "Be3", "Qd7", "Qd2", "O-O-O"]
SAME_SIDE = OPPOSITE[:-1] + ["O-O"]
# Tarrasch-style: Black ends up with an isolated d5 pawn; then shuffle until move 16.
IQP = ["d4", "d5", "c4", "e6", "Nc3", "c5", "cxd5", "exd5", "Nf3", "Nc6", "g3", "Nf6", "Bg2", "Be7", "O-O", "O-O",
       "dxc5", "Bxc5", "Na4", "Be7", "Nc3", "Bc5", "Na4", "Be7", "Nc3", "Bc5", "Na4", "Be7", "Nc3", "Bc5", "Na4", "Be7"]
# Seeded playout that trades queens and minor pieces down to a rook ending.
ROOK_END = ['h4', 'g5', 'Rh2', 'f6', 'f4', 'g4', 'c3', 'c6', 'b3', 'b6', 'd4', 'Ba6', 'f5', 'Qc8', 'Bh6', 'Nxh6', 'e4', 'Bxf1',
            'Kxf1', 'Nf7', 'Qc1', 'a6', 'Nf3', 'gxf3', 'e5', 'a5', 'Qg5', 'Nxe5', 'dxe5', 'fxg5', 'Kf2', 'gxh4', 'Rxh4', 'h5',
            'Kf1', 'Qa6+', 'Kg1', 'd5', 'exd6', 'Kf7', 'd7', 'Kg8', 'Ra4', 'Kf7', 'd8=B', 'Qb5', 'Bxb6', 'Qxa4', 'gxf3', 'Bg7',
            'bxa4', 'c5', 'Bxc5', 'Bxc3', 'Nxc3', 'e5', 'Kg2', 'Na6']
QUEEN_HANG = ["e4", "e5", "Qh5", "Nc6", "Qxe5+", "Nxe5"]  # White loses the queen for a pawn
LEVEL = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"]


def _pgn(moves, white="target", black="foe", white_elo=1500, black_elo=1500, eco=None):
    import chess

    board = chess.Board()
    parts = []
    for i, san in enumerate(moves):
        parts.append((f"{i // 2 + 1}. " if i % 2 == 0 else "") + san)
        board.push_san(san)
    eco_line = f'[ECOUrl "https://www.chess.com/openings/{eco}"]\n' if eco else ""
    return (f'[Event "Live Chess"]\n[White "{white}"]\n[Black "{black}"]\n[Result "*"]\n'
            f'[WhiteElo "{white_elo}"]\n[BlackElo "{black_elo}"]\n{eco_line}\n' + " ".join(parts) + " *")


def _raw(moves=None, *, color="white", own="win", foe=None, t=0, foe_name="foe", elo=(1500, 1500), end_time=None,
         white_acc=None, black_acc=None, eco=None):
    moves = moves or ["e4", "e5"]
    foe = foe or {"win": "resigned", "resigned": "win", "checkmated": "win", "timeout": "win", "agreed": "agreed"}[own]
    scouted_white = color == "white"
    white, black = ("target", foe_name) if scouted_white else (foe_name, "target")
    return {
        "white_username": white, "black_username": black,
        "white_result": own if scouted_white else foe, "black_result": foe if scouted_white else own,
        "white_accuracy": white_acc, "black_accuracy": black_acc,
        "end_time": T0 + t if end_time is None else end_time, "date": "2026-10-01", "time_class": "blitz",
        "time_control": "180", "rated": True, "rules": "chess", "url": f"https://www.chess.com/game/live/{t}",
        "pgn": _pgn(moves, white=white, black=black, white_elo=elo[0], black_elo=elo[1], eco=eco),
    }


def _pos(habits, key):
    return next((p for p in habits["positions"] if p["key"] == key), None)


# ── shape ─────────────────────────────────────────────────────────────────────


def test_empty_input_returns_all_keys():
    h = build_habits([], "target")
    assert set(h) == {"sessions", "time_of_day", "weekday", "positions", "resignation", "draws", "insights"}
    s = h["sessions"]
    assert s["sessions"] == 0 and s["avg_games_per_session"] is None and s["session_gap_minutes"] == 30
    for k in ("after_loss", "after_win", "after_draw", "on_losing_streak"):
        assert s[k]["games"] == 0 and s[k]["expected_pct"] is None and s[k]["shrunk_delta"] == 0.0
    assert [x["key"] for x in s["by_session_index"]] == ["1", "2", "3", "4-5", "6+"]
    assert [x["key"] for x in h["time_of_day"]] == ["night", "morning", "afternoon", "evening"]
    assert [x["key"] for x in h["weekday"]] == ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    assert h["positions"] == [] and h["insights"] == []
    assert h["draws"]["draws"] == 0 and h["draws"]["by_reason"] == []
    assert h["resignation"]["resignations"] == 0 and h["resignation"]["avg_material_at_resign"] is None


def test_games_without_the_user_or_other_variants_are_skipped():
    other = _raw()
    other["white_username"] = "someone"
    other["black_username"] = "else"
    variant = _raw()
    variant["rules"] = "chess960"
    h = build_habits([other, variant], "TARGET")
    assert h["sessions"]["sessions"] == 0


def test_username_match_is_case_insensitive():
    h = build_habits([_raw()], "TaRgEt")
    assert h["sessions"]["sessions"] == 1


# ── sessions ──────────────────────────────────────────────────────────────────


def test_session_splitting_and_after_loss_attribution():
    games = [
        _raw(own="resigned", t=0),            # session 1: loss
        _raw(own="win", t=600),               # session 1: win right after a loss
        _raw(own="resigned", t=600 + 3600),   # session 2 (gap > 30 min): loss, NOT after the win
        _raw(own="win", t=600 + 3600 + 300),  # session 2: win after a loss
    ]
    s = build_habits(games, "target")["sessions"]
    assert s["sessions"] == 2 and s["avg_games_per_session"] == 2.0
    assert s["after_loss"]["games"] == 2 and s["after_loss"]["score_pct"] == 100.0
    assert s["after_win"]["games"] == 0
    idx = {x["key"]: x["games"] for x in s["by_session_index"]}
    assert idx == {"1": 2, "2": 2, "3": 0, "4-5": 0, "6+": 0}


def test_after_win_after_draw_and_losing_streak():
    games = [
        _raw(own="resigned", t=0), _raw(own="resigned", t=60), _raw(own="win", t=120),   # win after 2 losses
        _raw(own="agreed", t=180), _raw(own="win", t=240),                               # draw after win, win after draw
    ]
    s = build_habits(games, "target")["sessions"]
    assert s["on_losing_streak"]["games"] == 1 and s["on_losing_streak"]["score_pct"] == 100.0
    assert s["after_win"]["games"] == 1      # the draw
    assert s["after_win"]["score_pct"] == 50.0
    assert s["after_draw"]["games"] == 1 and s["after_draw"]["score_pct"] == 100.0
    assert s["after_loss"]["games"] == 2


def test_session_index_buckets():
    games = [_raw(own="win", t=i * 60) for i in range(7)]
    idx = {x["key"]: x["games"] for x in build_habits(games, "target")["sessions"]["by_session_index"]}
    assert idx == {"1": 1, "2": 1, "3": 1, "4-5": 2, "6+": 2}


# ── time of day / weekday ─────────────────────────────────────────────────────


def test_timezone_shift_crosses_midnight():
    sun_2330_utc = int(datetime(2026, 10, 4, 23, 30, tzinfo=timezone.utc).timestamp())  # a Sunday
    game = _raw(end_time=sun_2330_utc)

    utc = build_habits([game], "target")
    assert {x["key"]: x["games"] for x in utc["time_of_day"]}["evening"] == 1
    assert {x["key"]: x["games"] for x in utc["weekday"]}["sun"] == 1

    sydney = build_habits([game], "target", tz_offset_minutes=600)  # 09:30 Monday
    assert {x["key"]: x["games"] for x in sydney["time_of_day"]}["morning"] == 1
    assert {x["key"]: x["games"] for x in sydney["weekday"]}["mon"] == 1
    assert {x["key"]: x["games"] for x in sydney["weekday"]}["sun"] == 0

    after_midnight = build_habits([game], "target", tz_offset_minutes=60)  # 00:30 Monday
    assert {x["key"]: x["games"] for x in after_midnight["time_of_day"]}["night"] == 1


# ── positions ─────────────────────────────────────────────────────────────────


def test_queenless_requires_queens_off_at_move_25_and_length():
    h = build_habits([_raw(_QUEENLESS, own="agreed")], "target")
    q = _pos(h, "queenless")
    assert q is not None and q["games"] == 1 and q["share"] == 100.0 and q["description"]
    # queens still on at move 25 -> not queenless
    long_with_queens = ["e4", "e5"] + ["Nf3", "Nc6", "Ng1", "Nb8"] * 15
    assert _pos(build_habits([_raw(long_with_queens, own="agreed")], "target"), "queenless") is None
    # queens off but the game is over right at move 25 -> not queenless
    short = _QUEENLESS[:52]
    assert _pos(build_habits([_raw(short, own="agreed")], "target"), "queenless") is None


def test_opposite_and_same_side_castling():
    opp = build_habits([_raw(OPPOSITE, own="win")], "target")
    assert _pos(opp, "opposite_castling")["games"] == 1
    assert _pos(opp, "same_side_castling") is None
    same = build_habits([_raw(SAME_SIDE, own="win")], "target")
    assert _pos(same, "same_side_castling")["games"] == 1
    assert _pos(same, "opposite_castling") is None


def test_isolated_queen_pawn_is_theirs_only():
    as_black = build_habits([_raw(IQP, color="black", own="win")], "target")
    assert _pos(as_black, "isolated_queen_pawn")["games"] == 1
    as_white = build_habits([_raw(IQP, color="white", own="win")], "target")
    assert _pos(as_white, "isolated_queen_pawn") is None


def test_rook_endgame_detected():
    h = build_habits([_raw(ROOK_END, own="win")], "target")
    keys = {p["key"] for p in h["positions"]}
    assert "rook_endgame" in keys
    assert not keys & {"queen_endgame", "pawn_endgame", "minor_piece_endgame"}


def test_positions_sorted_by_games_and_only_present_features():
    games = [_raw(OPPOSITE, own="win"), _raw(OPPOSITE, own="win", t=60), _raw(SAME_SIDE, own="win", t=120)]
    positions = build_habits(games, "target")["positions"]
    assert [p["games"] for p in positions] == sorted((p["games"] for p in positions), reverse=True)
    assert positions[0]["key"] == "opposite_castling" and positions[0]["share"] == 66.7
    assert all(p["games"] >= 1 for p in positions)


# ── resignation ───────────────────────────────────────────────────────────────


def test_resignation_with_level_material_vs_when_behind():
    games = [
        _raw(LEVEL, own="resigned", t=0),            # level material
        _raw(QUEEN_HANG, own="resigned", t=60),      # down a queen for a pawn
    ]
    r = build_habits(games, "target")["resignation"]
    assert r["resignations"] == 2
    assert r["resigned_not_behind"] == 1 and r["resigned_not_behind_pct"] == 50.0
    assert r["avg_material_at_resign"] == -4.0   # (0 + -8) / 2


def test_played_on_lost_counts_mate_and_time_losses_only():
    games = [
        _raw(QUEEN_HANG, own="timeout", t=0),
        _raw(QUEEN_HANG, own="checkmated", t=60),
        _raw(LEVEL, own="timeout", t=120),
        _raw(QUEEN_HANG, own="resigned", t=180),     # resignations are excluded
    ]
    r = build_habits(games, "target")["resignation"]
    assert r["played_on_lost"] == 2 and r["played_on_lost_pct"] == round(2 / 3 * 100, 1)


def test_comeback_and_collapse_detection():
    # White (scouted) is a queen down for a pawn but still wins -> comeback.
    comeback = build_habits([_raw(QUEEN_HANG, color="white", own="win"), _raw(LEVEL, own="win", t=60)], "target")["resignation"]
    assert comeback["comebacks"] == 1 and comeback["comeback_rate_pct"] == 100.0
    assert comeback["collapses_from_ahead"] == 0
    # Black (scouted) wins the queen but loses -> collapse; same game as White drawn -> comeback via draw.
    collapse = build_habits([_raw(QUEEN_HANG, color="black", own="resigned")], "target")["resignation"]
    assert collapse["collapses_from_ahead"] == 1 and collapse["collapse_rate_pct"] == 100.0
    assert collapse["comebacks"] == 0
    drawn = build_habits([_raw(QUEEN_HANG, color="white", own="agreed")], "target")["resignation"]
    assert drawn["comebacks"] == 1


def test_capture_recapture_is_not_a_material_swing():
    # The queen trade 3.Qxe5+ Qe7 4.Qxe7+ Bxe7 must not read as 9 points up/down mid-exchange.
    r = build_habits([_raw(_QUEENLESS[:8], own="resigned")], "target")["resignation"]
    assert r["comebacks"] == 0 and r["collapses_from_ahead"] == 0
    assert r["resigned_not_behind"] == 1   # White (scouted) is a pawn up at the end


# ── draws ─────────────────────────────────────────────────────────────────────


def test_draw_breakdown_and_agreed_as_favourite():
    games = [
        _raw(own="agreed", t=0, elo=(1700, 1500)),          # agreed as the favourite
        _raw(own="agreed", t=60, elo=(1500, 1700)),         # agreed as the underdog
        _raw(own="win", foe="repetition", t=120),           # not a draw (they won)
        _raw(own="repetition", foe="repetition", t=180),
        _raw(own="win", t=240),
    ]
    d = build_habits(games, "target")["draws"]
    assert d["draws"] == 3 and d["draw_rate_pct"] == 60.0
    assert d["agreed_as_favourite"] == 1
    assert {r["reason"]: r["games"] for r in d["by_reason"]} == {"agreed": 2, "repetition": 1}


# ── insights ──────────────────────────────────────────────────────────────────


def test_insights_require_minimum_sample_and_flag_tilt():
    # 10 pairs (loss, then another loss) inside separate sessions: they always lose after a loss.
    games = []
    for i in range(10):
        base = i * 7200
        games.append(_raw(own="resigned", t=base))
        games.append(_raw(own="resigned", t=base + 120))
    h = build_habits(games, "target")
    assert any(s.startswith("Tilts:") for s in h["insights"])
    assert 1 <= len(h["insights"]) <= 7

    # Same behaviour on a tiny sample must not produce a tilt claim.
    small = build_habits(games[:6], "target")
    assert not any(s.startswith("Tilts:") for s in small["insights"])


def test_resign_early_insight():
    games = [_raw(LEVEL, own="resigned", t=i * 7200) for i in range(10)]
    assert any(s.startswith("Resigns early") for s in build_habits(games, "target")["insights"])


# ── head to head ──────────────────────────────────────────────────────────────


def test_head_to_head_none_when_never_played():
    assert build_head_to_head([_raw(foe_name="stranger")], "target", "me") is None
    assert build_head_to_head([], "target", "me") is None


def test_head_to_head_pov_and_repeated_lines():
    line = ["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5", "Ng3", "Bg6"]
    eco = "Caro-Kann-Defense-Advance-Variation"
    games = [
        # me (white) beat target: target is black and lost
        _raw(line, color="black", own="resigned", foe_name="Me", t=0, elo=(1600, 1500), white_acc=90.0, black_acc=70.0, eco=eco),
        # me (white) lost: target black won
        _raw(line, color="black", own="win", foe_name="ME", t=60, elo=(1600, 1500), white_acc=80.0, black_acc=85.0, eco=eco),
        # me (black) drew with target (white)
        _raw(["d4", "d5"], color="white", own="agreed", foe_name="me", t=120, elo=(1500, 1600), white_acc=None, black_acc=None),
        _raw(["e4", "e5"], color="white", own="agreed", foe_name="someone_else", t=180),
    ]
    h = build_head_to_head(games, "target", "me")
    assert h["me"] == "me" and h["games"] == 3
    assert (h["wins"], h["draws"], h["losses"]) == (1, 1, 1)
    assert h["score_pct"] == 50.0
    assert h["your_avg_accuracy"] == 85.0 and h["their_avg_accuracy"] == 77.5
    assert h["you_white"]["games"] == 2 and h["you_white"]["score_pct"] == 50.0
    assert h["you_black"]["games"] == 1 and h["you_black"]["score_pct"] == 50.0
    # Expected is from MY rating vs theirs: I am 1600 against 1500 in every game.
    assert h["you_white"]["expected_pct"] == h["you_black"]["expected_pct"] == 64.0
    assert len(h["repeated_lines"]) == 1
    rl = h["repeated_lines"][0]
    assert rl["games"] == 2 and rl["your_score_pct"] == 50.0
    assert rl["path"] == line[:8] and rl["line"] == "1. e4 c6 2. d4 d5 3. Nc3 dxe4 4. Nxe4 Bf5"
    assert h["recent"][0]["result"] == "draw" and h["recent"][0]["you_color"] == "black"
    assert h["recent"][1]["you_color"] == "white" and h["recent"][1]["result"] == "loss"
    assert h["recent"][1]["opening"].startswith("Caro")
    assert 2 <= len(h["insights"]) <= 4


def test_head_to_head_recent_capped_at_ten():
    games = [_raw(own="win", foe_name="me", t=i) for i in range(14)]
    h = build_head_to_head(games, "target", "me")
    assert h["games"] == 14 and len(h["recent"]) == 10
    # target won every game -> I lost every game
    assert h["losses"] == 14 and h["score_pct"] == 0.0
