"""Unit tests for the pure drill-activity trend on the progress dashboard.

Covers the windowing (this-week vs last-week) and headline selection in
:func:`backend.services.progress.summarize_training_activity` — no DB, no engine.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

# The pure modules import backend.db at module load; APP_ENV=dev skips DATABASE_URL.
os.environ.setdefault("APP_ENV", "dev")

from backend.services.progress import summarize_training_activity  # noqa: E402

NOW = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)


def _attempt(*, days_ago: float, verdict: str, phase: str | None = None) -> dict:
    return {
        "verdict": verdict,
        "played_at": NOW - timedelta(days=days_ago),
        "swing_cp": None,
        "phase": phase,
        "category": "x",
    }


def test_empty_is_inactive_no_headline():
    result = summarize_training_activity([], now=NOW)
    assert result["active"] is False
    assert result["headline"] is None
    assert result["this_week"] == {"attempts": 0, "passed": 0}
    assert result["passed_delta"] == 0


def test_buckets_this_week_vs_last_week():
    attempts = [
        _attempt(days_ago=1, verdict="pass"),
        _attempt(days_ago=3, verdict="fail"),
        _attempt(days_ago=10, verdict="pass"),  # last week
        _attempt(days_ago=20, verdict="pass"),  # outside both windows
    ]
    result = summarize_training_activity(attempts, now=NOW)
    assert result["this_week"] == {"attempts": 2, "passed": 1}
    assert result["last_week"] == {"attempts": 1, "passed": 1}
    assert result["passed_delta"] == 0  # 1 this week - 1 last week
    assert result["active"] is True


def test_headline_names_most_drilled_phase():
    attempts = [
        _attempt(days_ago=1, verdict="pass", phase="Endgame"),
        _attempt(days_ago=2, verdict="pass", phase="Endgame"),
        _attempt(days_ago=2, verdict="pass", phase="Middlegame"),
    ]
    result = summarize_training_activity(attempts, now=NOW)
    assert result["top_phase"] == "Endgame"
    assert result["top_phase_passed"] == 2
    assert result["headline"] == "You've passed 2 endgame drills this week"


def test_headline_singular_phase():
    result = summarize_training_activity(
        [_attempt(days_ago=1, verdict="pass", phase="Opening")], now=NOW
    )
    assert result["headline"] == "You've passed 1 opening drill this week"


def test_headline_falls_back_to_total_without_phase():
    attempts = [
        _attempt(days_ago=1, verdict="pass"),
        _attempt(days_ago=2, verdict="pass"),
    ]
    result = summarize_training_activity(attempts, now=NOW)
    assert result["top_phase"] is None
    assert result["headline"] == "You've passed 2 drills this week"


def test_failed_attempts_count_as_activity_but_no_headline():
    result = summarize_training_activity(
        [_attempt(days_ago=1, verdict="fail")], now=NOW
    )
    assert result["active"] is True
    assert result["this_week"] == {"attempts": 1, "passed": 0}
    assert result["headline"] is None


def test_window_boundary_is_inclusive_lower_exclusive_split():
    # Exactly 7 days ago is the start of "this week" (>= this_start).
    result = summarize_training_activity(
        [_attempt(days_ago=7, verdict="pass")], now=NOW
    )
    assert result["this_week"]["passed"] == 1
    assert result["last_week"]["passed"] == 0
