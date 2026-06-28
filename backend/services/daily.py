"""Daily puzzle set, spaced repetition scheduling, and streak transitions.

The arithmetic here is pure and deterministic (interval ladder + streak rules);
all reads/writes go through :mod:`backend.repositories.srs`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..repositories import srs as srs_repo

# Re-show ladder, indexed by interval_stage. A pass advances the stage (longer
# gap); a fail drops back to stage 0 (re-show tomorrow). Capped at the last stage.
SRS_INTERVALS_DAYS = [1, 3, 7]

DAILY_SET_SIZE = 5


def next_schedule(stage: int | None, result: str, today: date) -> tuple[int, date]:
    """Pure: given the current stage and a pass/fail, return (new_stage, due_date).

    - pass: advance one stage (clamped to the last), schedule that interval out.
    - fail: reset to stage 0 (re-show in +1 day).
    """
    current = stage or 0
    if result == "pass":
        new_stage = min(current + 1, len(SRS_INTERVALS_DAYS) - 1)
    else:
        new_stage = 0
    due = today + timedelta(days=SRS_INTERVALS_DAYS[new_stage])
    return new_stage, due


def advance_streak(
    current_streak: int,
    longest_streak: int,
    last_completed: date | None,
    today: date,
) -> tuple[int, int]:
    """Pure: streak transition when the daily set is completed on ``today``.

    Same calendar day → unchanged (idempotent). Consecutive day → +1. Any gap (or
    first ever) → reset to 1. ``longest`` is the running maximum.
    """
    if last_completed == today:
        new_current = current_streak
    elif last_completed == today - timedelta(days=1):
        new_current = current_streak + 1
    else:
        new_current = 1
    return new_current, max(longest_streak, new_current)


# ── orchestration ───────────────────────────────────────────────────────────

def get_daily(device_id: str, today: date) -> dict[str, Any]:
    """Today's set + due SRS cards + streak, scoped to the device."""
    return {
        "date": today.isoformat(),
        "daily_set": srs_repo.get_daily_puzzles(device_id, limit=DAILY_SET_SIZE),
        "due_cards": srs_repo.get_due_cards(device_id, today),
        "streak": srs_repo.get_streak(device_id),
    }


def record_result(
    device_id: str,
    username: str | None,
    puzzle_id: int,
    result: str,
    today: date,
) -> dict[str, Any]:
    """Schedule the puzzle's next SRS appearance and roll the streak forward.

    Completing the daily set is approximated as "got a result on a daily puzzle
    today" — the streak advances at most once per calendar day (the transition is
    idempotent within a day).
    """
    stage = srs_repo.get_card_stage(device_id, puzzle_id)
    new_stage, due = next_schedule(stage, result, today)
    srs_repo.upsert_card(
        device_id,
        username,
        puzzle_id,
        interval_stage=new_stage,
        due_date=due,
        last_result=result,
    )

    streak = srs_repo.get_streak(device_id)
    last = date.fromisoformat(streak["last_completed_date"]) if streak["last_completed_date"] else None
    new_current, new_longest = advance_streak(
        streak["current_streak"], streak["longest_streak"], last, today
    )
    srs_repo.save_streak(
        device_id,
        current_streak=new_current,
        longest_streak=new_longest,
        last_completed_date=today,
    )

    return {
        "scheduled": {"interval_stage": new_stage, "due_date": due.isoformat(), "last_result": result},
        "streak": {
            "current_streak": new_current,
            "longest_streak": new_longest,
            "last_completed_date": today.isoformat(),
        },
    }
