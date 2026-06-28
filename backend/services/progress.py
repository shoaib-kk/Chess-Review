"""Progress-over-time summary: "your number that moved".

Reuses :func:`get_player_insights` (its ``trend_points``) as the single source of
truth for per-game accuracy/blunder data, then diffs the most recent window
against the preceding one to produce human deltas for the home dashboard. Cached
with :func:`ttl_lru_cache` like the other chess.com-backed lookups.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any

from .cache import ttl_lru_cache
from .player_insights import get_player_insights

WINDOW = 30  # games per comparison window ("this month" vs "last month")
TRAINING_WINDOW_DAYS = 7  # drill-activity comparison window ("this week" vs "last week")


def _window_metrics(points: list[dict[str, Any]]) -> dict[str, Any]:
    games = len(points)
    accuracies = [p["accuracy"] for p in points if p.get("accuracy") is not None]
    blunders = sum(p.get("blunders", 0) for p in points)
    return {
        "games": games,
        "avg_accuracy": round(mean(accuracies), 1) if accuracies else None,
        "blunders": blunders,
        "blunder_rate": round(blunders / games * 100, 1) if games else None,
    }


def _delta(label: str, current: float | None, previous: float | None, *, unit: str, relative: bool, good_when_down: bool) -> dict[str, Any] | None:
    if current is None or previous is None:
        return None
    raw = current - previous
    if relative:
        if previous == 0:
            return None
        change = round((raw / previous) * 100, 0)
    else:
        change = round(raw, 1)
    if change == 0:
        direction = "flat"
    elif change > 0:
        direction = "up"
    else:
        direction = "down"

    improved = (direction == "down") if good_when_down else (direction == "up")
    arrow = "↑" if direction == "up" else "↓" if direction == "down" else "→"
    magnitude = abs(change)
    text = f"{label} {arrow} {magnitude:g}{unit} vs last month" if direction != "flat" else f"{label} unchanged vs last month"
    return {
        "label": label,
        "direction": direction,
        "improved": improved,
        "change": change,
        "unit": unit,
        "text": text,
    }


@ttl_lru_cache(maxsize=32, ttl_seconds=300)
def get_progress_summary(username: str) -> dict[str, Any]:
    """Insights-derived progress deltas for a username (streak added by the router)."""
    insights = get_player_insights(username=username)
    points = insights.get("performance", {}).get("trend_points", []) or []
    # trend_points run oldest -> newest; compare the latest window to the prior one.
    current_points = points[-WINDOW:]
    previous_points = points[-2 * WINDOW : -WINDOW]

    current = _window_metrics(current_points)
    previous = _window_metrics(previous_points)

    deltas = [
        d
        for d in (
            _delta("Accuracy", current["avg_accuracy"], previous["avg_accuracy"], unit=" pts", relative=False, good_when_down=False),
            _delta("Blunder rate", current["blunder_rate"], previous["blunder_rate"], unit="%", relative=True, good_when_down=True),
        )
        if d is not None
    ]

    return {
        "username": insights.get("username", username),
        "current_window": current,
        "previous_window": previous,
        "deltas": deltas,
        "has_comparison": bool(previous["games"]),
    }


# ── training activity (device-scoped, not username-cached) ───────────────────
#
# The game-window deltas above only move once a user has played ~30 new games,
# which is a motivation dead-end for the users who drill the hardest. This trend
# is derived directly from their graded play-out attempts so the dashboard reacts
# to *training* — "you've passed N endgame drills this week" — within days.


def _training_headline(passed: int, top_phase: str | None, top_phase_passed: int) -> str | None:
    if passed <= 0:
        return None
    if top_phase and top_phase_passed > 0:
        noun = "drill" if top_phase_passed == 1 else "drills"
        return f"You've passed {top_phase_passed} {top_phase.lower()} {noun} this week"
    noun = "drill" if passed == 1 else "drills"
    return f"You've passed {passed} {noun} this week"


def summarize_training_activity(
    attempts: list[dict[str, Any]],
    *,
    now: datetime,
    window_days: int = TRAINING_WINDOW_DAYS,
) -> dict[str, Any]:
    """Pure: bucket drill attempts into this-week vs last-week and pick a headline.

    ``attempts`` are raw rows (verdict / played_at / phase) from
    :func:`backend.repositories.drills.get_recent_attempts`. The most-drilled
    phase this week drives the headline so the message is specific.
    """
    this_start = now - timedelta(days=window_days)
    last_start = now - timedelta(days=2 * window_days)

    this_week = {"attempts": 0, "passed": 0}
    last_week = {"attempts": 0, "passed": 0}
    phase_passed: dict[str, int] = {}

    for attempt in attempts:
        played_at = attempt["played_at"]
        passed = attempt.get("verdict") == "pass"
        if played_at >= this_start:
            this_week["attempts"] += 1
            if passed:
                this_week["passed"] += 1
                phase = attempt.get("phase")
                if phase:
                    phase_passed[phase] = phase_passed.get(phase, 0) + 1
        elif played_at >= last_start:
            last_week["attempts"] += 1
            if passed:
                last_week["passed"] += 1

    top_phase: str | None = None
    top_phase_passed = 0
    if phase_passed:
        top_phase, top_phase_passed = max(phase_passed.items(), key=lambda kv: kv[1])

    return {
        "this_week": this_week,
        "last_week": last_week,
        "passed_delta": this_week["passed"] - last_week["passed"],
        "top_phase": top_phase,
        "top_phase_passed": top_phase_passed,
        "headline": _training_headline(this_week["passed"], top_phase, top_phase_passed),
        "active": this_week["attempts"] > 0,
    }


def get_training_activity(
    device_id: str,
    *,
    now: datetime | None = None,
    window_days: int = TRAINING_WINDOW_DAYS,
) -> dict[str, Any]:
    """Device-scoped drill-activity trend for the progress dashboard."""
    # Imported here to keep the module-level import graph free of the repository
    # layer (which imports other services).
    from ..repositories.drills import get_recent_attempts

    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=2 * window_days)
    attempts = get_recent_attempts(device_id, since)
    return summarize_training_activity(attempts, now=now, window_days=window_days)
