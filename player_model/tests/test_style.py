"""Unit tests for the Phase 6 style embedding layer."""

from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="pm_style_")
os.environ["PM_MODELS_DIR"] = os.path.join(_TMP, "models")
os.environ["PM_DATABASE_URL"] = "sqlite:///" + os.path.join(_TMP, "style_test.db")
os.environ["STYLE_PCA_COMPONENTS"] = "8"

import numpy as np  # noqa: E402

from player_model import style_embedding as S  # noqa: E402

N_PLAYERS = 12


def _make_features(values: dict) -> dict:
    g = values.get
    return {
        "accuracy": {
            "mean_cpl": g("mean_cpl"), "cpl_std": g("cpl_std"),
            "accuracy_variance_across_games": g("accuracy_variance_across_games"),
            "blunder_rate": g("blunder_rate"), "mistake_rate": g("mistake_rate"),
        },
        "tactical": {
            "brilliant_move_rate": g("brilliant_move_rate"),
            "tactical_opportunity_conversion": g("tactical_opportunity_conversion"),
            "sacrifice_tendency": g("sacrifice_tendency"),
            "complexity_preference": g("complexity_preference"),
        },
        "style": {
            "aggression_index": g("aggression_index"),
            "queen_trade_avoidance": g("queen_trade_avoidance"),
            "initiative_index": g("initiative_index"),
            "trade_preference_by_piece": {
                "Q": g("trade_preference_Q"), "R": g("trade_preference_R"),
                "B": g("trade_preference_B"), "N": g("trade_preference_N"),
            },
        },
        "endgame": {
            "endgame_accuracy": g("endgame_accuracy"),
            "endgame_conversion_rate": g("endgame_conversion_rate"),
        },
        "opening": {
            "opening_flexibility": g("opening_flexibility"),
            "opening_accuracy": g("opening_accuracy"),
        },
        "positional": {
            "piece_activity_index": g("piece_activity_index"),
            "king_safety_index": g("king_safety_index"),
        },
    }


def _seed_players(null_player_complexity: bool = True):
    from player_model.db import SessionLocal, init_db
    from player_model.models import Player, PlayerProfile

    init_db()
    db = SessionLocal()
    # Tests share one SQLite file; start each seed from a clean slate.
    from player_model.models import PlayerStyleVector
    db.query(PlayerStyleVector).delete()
    db.query(PlayerProfile).delete()
    db.query(Player).delete()
    db.commit()
    rng = np.random.default_rng(0)
    prototypes = rng.normal(size=(4, len(S.FEATURE_NAMES)))  # low-rank structure

    ids = []
    for i in range(N_PLAYERS):
        raw = prototypes[i % 4] + 0.1 * rng.normal(size=len(S.FEATURE_NAMES))
        values = {name: float(raw[j]) for j, name in enumerate(S.FEATURE_NAMES)}
        if null_player_complexity and i == 0:
            values["complexity_preference"] = None  # exercises median imputation
        player = Player(username=f"style_user_{i}")
        db.add(player)
        db.flush()
        db.add(PlayerProfile(player_id=player.id, features=_make_features(values),
                             game_count=20))
        ids.append(player.id)
    db.commit()
    db.close()
    return ids


def _db():
    from player_model.db import SessionLocal

    return SessionLocal()


# --------------------------------------------------------------------------- #
def test_extract_feature_row_handles_nulls():
    row = S.extract_feature_row({"accuracy": {"mean_cpl": 30}})
    assert len(row) == len(S.FEATURE_NAMES) == 22
    assert row[0] == 30.0                       # mean_cpl
    assert row[1] is None                       # cpl_std missing -> None


def test_build_feature_matrix_imputes_median():
    ids = _seed_players()                       # ids[0] has null complexity_preference
    db = _db()
    try:
        matrix, player_ids, names = S.build_feature_matrix(db)
        assert matrix.shape == (N_PLAYERS, 22)
        assert names == S.FEATURE_NAMES
        assert set(player_ids) == set(ids)

        # The null player's complexity_preference is imputed to the column median.
        cj = names.index("complexity_preference")
        null_row = player_ids.index(ids[0])
        others = [matrix[i, cj] for i in range(N_PLAYERS) if i != null_row]
        assert abs(matrix[null_row, cj] - float(np.median(others))) < 1e-9, (
            f"got {matrix[null_row, cj]} vs median {float(np.median(others))}; "
            f"n={len(player_ids)}"
        )
        assert os.path.exists(S._path("scaler.pkl"))   # scaler persisted by build
    finally:
        db.close()


def test_fit_and_compute_vectors():
    _seed_players()
    db = _db()
    try:
        result = S.fit_style_embeddings(db)
        assert result["players"] == N_PLAYERS
        assert result["version"] >= 1
        ncomp = result["n_components"]

        from player_model.models import PlayerStyleVector
        rows = db.query(PlayerStyleVector).all()
        assert len(rows) == N_PLAYERS
        assert all(len(r.vector) == ncomp for r in rows)
        assert all(r.pca_version == result["version"] for r in rows)

        # compute_style_vector reproduces the stored embedding.
        pid = rows[0].player_id
        vec = S.compute_style_vector(pid, db)
        stored = db.get(PlayerStyleVector, pid).vector
        assert np.allclose(vec, stored, atol=1e-6)
    finally:
        db.close()


def test_find_similar_players():
    _seed_players()
    db = _db()
    try:
        S.fit_style_embeddings(db)
        from player_model.models import PlayerStyleVector
        pid = db.query(PlayerStyleVector).first().player_id

        sims = S.find_similar_players(pid, db, top_k=3)
        assert len(sims) == 3
        assert all(s.player_id != pid for s in sims)             # excludes self
        cos = [s.cosine_similarity for s in sims]
        assert cos == sorted(cos, reverse=True)                  # sorted desc
        assert all(-1.0001 <= c <= 1.0001 for c in cos)
    finally:
        db.close()


def test_cluster_players_assigns_archetypes():
    _seed_players()
    db = _db()
    try:
        S.fit_style_embeddings(db)
        out = S.cluster_players(db, n_clusters=4)
        assert out["assignments"]
        assert all(a in S.ARCHETYPES for a in out["assignments"].values())

        from player_model.models import PlayerProfile
        profiles = db.query(PlayerProfile).all()
        assert all(p.archetype in S.ARCHETYPES for p in profiles)
    finally:
        db.close()


def test_compare_players():
    _seed_players()
    db = _db()
    try:
        S.fit_style_embeddings(db)
        from player_model.models import PlayerStyleVector
        ids = [r.player_id for r in db.query(PlayerStyleVector).all()]

        out = S.compare_players(ids[0], ids[1], db)
        assert set(out) == {"cosine_similarity", "dimension_diff", "dominant_differences"}
        assert -1.0001 <= out["cosine_similarity"] <= 1.0001
        assert len(out["dimension_diff"]) >= 1
        assert len(out["dominant_differences"]) <= 5
        if out["dominant_differences"]:
            assert set(out["dominant_differences"][0]) == {"feature", "player_a", "player_b"}
    finally:
        db.close()


def test_should_refit_thresholds():
    assert S.should_refit(49, 55) is True       # crosses 50
    assert S.should_refit(60, 70) is False
    assert S.should_refit(450, 2100) is True    # crosses 500 and 2000
    assert S.should_refit(200, 200) is False    # already at threshold


def test_visualization_writes_png():
    _seed_players()
    db = _db()
    try:
        S.fit_style_embeddings(db)
        S.cluster_players(db, n_clusters=4)
    finally:
        db.close()

    from player_model.style_visualize import plot_style_scatter

    out = os.path.join(_TMP, "scatter.png")
    path = plot_style_scatter(out)
    assert os.path.exists(path) and os.path.getsize(path) > 0


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            import traceback
            failed += 1
            print(f"ERROR {t.__name__}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
