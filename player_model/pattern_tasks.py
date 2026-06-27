"""Celery task that detects behavioural patterns after a profile is computed."""

from __future__ import annotations

import logging

from .celery_app import celery_app
from .db import SessionLocal
from .patterns import compute_behavioural_patterns

logger = logging.getLogger(__name__)


@celery_app.task(name="player_model.compute_patterns")
def compute_patterns(player_id: int) -> dict:
    """Detect and persist behavioural patterns for a player.

    Triggered automatically once ``compute_profile`` finishes (see
    ``profile_tasks.compute_profile``).
    """
    db = SessionLocal()
    try:
        logger.info("Detecting behavioural patterns for player_id=%s", player_id)
        patterns = compute_behavioural_patterns(player_id, db)
        logger.info("Found %d patterns for player_id=%s", len(patterns), player_id)
        return {"player_id": player_id, "pattern_count": len(patterns)}
    finally:
        db.close()
