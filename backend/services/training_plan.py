"""Training-plan assembly: weaknesses -> categories -> drill sets with progress.

Thin orchestration over :func:`get_player_insights` (the source of truth for
*what* the weaknesses are), the pure category derivation in
:mod:`backend.services.drills`, and the drills repository (persistence + progress).
"""

from __future__ import annotations

import logging
from typing import Any

from ..repositories import drills as drills_repo
from .drills import MAX_USER_MOVES, derive_categories
from .player_insights import get_player_insights

logger = logging.getLogger(__name__)


def get_training_plan(device_id: str, username: str) -> dict[str, Any]:
    """Build the device's training plan from the player's weaknesses.

    Categories are derived from the user's insights; each category's drill set is
    generated (idempotently) from the user's already-mined puzzles, so a plan is
    only as full as the puzzle mining the user has run.
    """
    insights = get_player_insights(username=username)
    specs = derive_categories(insights)

    categories = []
    for spec in specs:
        total = drills_repo.ensure_drills_for_category(device_id, username, spec)
        progress = drills_repo.get_category_progress(device_id, spec.name)
        categories.append(
            {
                "name": spec.name,
                "weakness_source": spec.weakness_source,
                "phase": spec.phase,
                "drills_total": progress["drills_total"],
                "drills_passed": progress["drills_passed"],
                "mastery_pct": progress["mastery_pct"],
                "mastered": progress["mastered"],
                "next_drill_id": progress["next_drill_id"],
            }
        )

    return {
        "username": insights.get("username", username),
        "max_user_moves": MAX_USER_MOVES,
        "categories": categories,
    }
