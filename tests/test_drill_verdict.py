"""Unit tests for the deterministic drill verdict + scheduling logic.

These cover the pure functions only (no DB, no engine): given start_eval /
objective / final_eval, the verdict must be predictable, and the SRS interval
ladder + streak transitions must follow the documented rules.
"""

from __future__ import annotations

import os
from datetime import date

import pytest

# The pure modules import backend.db at module load (engine creation, no connect),
# which requires a DATABASE_URL unless APP_ENV=dev. Set it before importing.
os.environ.setdefault("APP_ENV", "dev")

from backend.services.daily import (  # noqa: E402
    SRS_INTERVALS_DAYS,
    advance_streak,
    next_schedule,
)
from backend.services.drills import (  # noqa: E402
    SLIP_TOLERANCE_CP,
    WINNING_THRESHOLD_CP,
    compute_verdict,
    objective_for,
)


# ── objective_for ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "start_eval, expected",
    [
        (WINNING_THRESHOLD_CP, "convert"),
        (300, "convert"),
        (0, "hold"),
        (149, "hold"),
        (-149, "hold"),
        (-WINNING_THRESHOLD_CP, "defend"),
        (-400, "defend"),
    ],
)
def test_objective_for(start_eval, expected):
    assert objective_for(start_eval) == expected


# ── compute_verdict: convert ────────────────────────────────────────────────

def test_convert_pass_when_advantage_held():
    r = compute_verdict("convert", 300, 250)
    assert r.verdict == "pass"
    assert r.swing == -50


def test_convert_pass_at_exact_tolerance_floor():
    # final == start - 100 is still a pass (>= floor).
    r = compute_verdict("convert", 300, 300 - SLIP_TOLERANCE_CP)
    assert r.verdict == "pass"


def test_convert_fail_when_advantage_thrown():
    r = compute_verdict("convert", 300, 150)
    assert r.verdict == "fail"
    assert r.swing == -150


def test_convert_pass_on_mate_even_if_eval_missing():
    r = compute_verdict("convert", 300, None, mate_for_user=True)
    assert r.verdict == "pass"
    assert r.swing is None
    assert "checkmate" in r.reason.lower()


# ── compute_verdict: hold ───────────────────────────────────────────────────

def test_hold_pass_when_balance_kept():
    assert compute_verdict("hold", 0, -80).verdict == "pass"


def test_hold_fail_when_position_worsens():
    assert compute_verdict("hold", 0, -150).verdict == "fail"


# ── compute_verdict: defend ─────────────────────────────────────────────────

def test_defend_pass_on_draw():
    r = compute_verdict("defend", -400, -600, is_draw=True)
    assert r.verdict == "pass"


def test_defend_pass_when_not_made_worse():
    assert compute_verdict("defend", -300, -350).verdict == "pass"


def test_defend_fail_when_deteriorates():
    assert compute_verdict("defend", -300, -500).verdict == "fail"


# ── compute_verdict: missing eval never passes (without mate/draw) ───────────

def test_missing_final_eval_fails_when_no_terminal_signal():
    assert compute_verdict("hold", 0, None).verdict == "fail"
    assert compute_verdict("convert", 300, None).verdict == "fail"


# ── SRS interval ladder ─────────────────────────────────────────────────────

def test_srs_pass_advances_stage():
    today = date(2026, 6, 28)
    stage, due = next_schedule(0, "pass", today)
    assert stage == 1
    assert due == date(2026, 7, 1)  # +3 days (stage 1)


def test_srs_pass_caps_at_last_stage():
    today = date(2026, 6, 28)
    stage, due = next_schedule(2, "pass", today)
    assert stage == len(SRS_INTERVALS_DAYS) - 1 == 2
    assert (due - today).days == SRS_INTERVALS_DAYS[2] == 7


def test_srs_fail_resets_to_stage_zero():
    today = date(2026, 6, 28)
    stage, due = next_schedule(2, "fail", today)
    assert stage == 0
    assert (due - today).days == 1


# ── streak transitions ──────────────────────────────────────────────────────

def test_streak_first_completion():
    cur, longest = advance_streak(0, 0, None, date(2026, 6, 28))
    assert (cur, longest) == (1, 1)


def test_streak_consecutive_day_increments():
    cur, longest = advance_streak(5, 9, date(2026, 6, 27), date(2026, 6, 28))
    assert cur == 6
    assert longest == 9  # unchanged, still below record


def test_streak_same_day_idempotent():
    cur, longest = advance_streak(6, 9, date(2026, 6, 28), date(2026, 6, 28))
    assert (cur, longest) == (6, 9)


def test_streak_gap_resets_and_updates_record():
    cur, longest = advance_streak(6, 6, date(2026, 6, 25), date(2026, 6, 28))
    assert cur == 1
    assert longest == 6


def test_streak_new_record_tracked():
    cur, longest = advance_streak(9, 9, date(2026, 6, 27), date(2026, 6, 28))
    assert cur == 10
    assert longest == 10
