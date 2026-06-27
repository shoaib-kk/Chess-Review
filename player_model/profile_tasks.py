"""Celery task that builds a player profile once ingestion completes."""

from __future__ import annotations

import logging

from .celery_app import celery_app
from .db import SessionLocal
from .features import compute_player_profile

logger = logging.getLogger(__name__)


@celery_app.task(name="player_model.compute_profile")
def compute_profile(player_id: int) -> dict:
    """Compute and persist the structured profile for a player.

    Triggered automatically when an ingestion job finishes (see
    ``tasks.ingest_pgn``). Updates ``player_profiles.computed_at`` via the upsert
    in :func:`compute_player_profile`.
    """
    db = SessionLocal()
    try:
        logger.info("Computing player profile for player_id=%s", player_id)
        features = compute_player_profile(player_id, db)
        logger.info("Profile computed for player_id=%s", player_id)

        # Phase 5: (re)build the position similarity index. Best-effort — a failure
        # here must not block pattern detection.
        try:
            from .index_manager import build_position_index

            build_position_index(player_id, db)
            logger.info("Position index built for player_id=%s", player_id)
        except Exception:  # noqa: BLE001
            logger.exception("Index build failed for player_id=%s", player_id)

        # Phase 6: keep the style embedding fresh. Refit (+ recluster) when a
        # player-count threshold is crossed; otherwise just embed this player.
        try:
            from .style_embedding import (
                cluster_players,
                compute_style_vector,
                model_exists,
                refit_if_needed,
            )

            refit = refit_if_needed(db)
            if refit is not None:
                cluster_players(db)
            elif model_exists():
                compute_style_vector(player_id, db)
        except Exception:  # noqa: BLE001
            logger.exception("Style embedding update failed for player_id=%s", player_id)

        # Profile done -> kick off Phase 3 behavioural pattern detection.
        from .pattern_tasks import compute_patterns

        compute_patterns.delay(player_id)
        return {"player_id": player_id, "groups": list(features.keys())}
    finally:
        db.close()
