"""Player style embeddings via PCA (Phase 6).

Turns each player's Phase 2 feature dict into a compact style vector that powers
player-similarity search, archetype clustering and style comparison. PCA is the
deliberate MVP choice: no training data, interpretable, fast.

Artifacts are persisted under ``PM_MODELS_DIR`` (default ``/data/models``):
  scaler.pkl       — fitted StandardScaler
  medians.pkl      — per-feature medians (for imputing a single player's nulls)
  style_pca.pkl    — fitted PCA
  pca_meta.json    — {"version", "n_components", "feature_names", "player_count"}
"""

from __future__ import annotations

import json
import os
import pickle
import warnings
from dataclasses import asdict, dataclass

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

MODELS_DIR = os.getenv("PM_MODELS_DIR", "/data/models")
DEFAULT_COMPONENTS = int(os.getenv("STYLE_PCA_COMPONENTS", "8"))
EXPLAINED_VARIANCE_TARGET = 0.75
FALLBACK_COMPONENTS = 12
REFIT_THRESHOLDS = (50, 200, 500, 2000)

# Feature name -> path in the nested Phase 2 feature blob.
FEATURE_PATHS: list[tuple[str, tuple]] = [
    ("mean_cpl", ("accuracy", "mean_cpl")),
    ("cpl_std", ("accuracy", "cpl_std")),
    ("accuracy_variance_across_games", ("accuracy", "accuracy_variance_across_games")),
    ("blunder_rate", ("accuracy", "blunder_rate")),
    ("mistake_rate", ("accuracy", "mistake_rate")),
    ("brilliant_move_rate", ("tactical", "brilliant_move_rate")),
    ("tactical_opportunity_conversion", ("tactical", "tactical_opportunity_conversion")),
    ("sacrifice_tendency", ("tactical", "sacrifice_tendency")),
    ("complexity_preference", ("tactical", "complexity_preference")),
    ("aggression_index", ("style", "aggression_index")),
    ("queen_trade_avoidance", ("style", "queen_trade_avoidance")),
    ("initiative_index", ("style", "initiative_index")),
    ("endgame_accuracy", ("endgame", "endgame_accuracy")),
    ("endgame_conversion_rate", ("endgame", "endgame_conversion_rate")),
    ("opening_flexibility", ("opening", "opening_flexibility")),
    ("opening_accuracy", ("opening", "opening_accuracy")),
    ("piece_activity_index", ("positional", "piece_activity_index")),
    ("king_safety_index", ("positional", "king_safety_index")),
    ("trade_preference_Q", ("style", "trade_preference_by_piece", "Q")),
    ("trade_preference_R", ("style", "trade_preference_by_piece", "R")),
    ("trade_preference_B", ("style", "trade_preference_by_piece", "B")),
    ("trade_preference_N", ("style", "trade_preference_by_piece", "N")),
]
FEATURE_NAMES = [name for name, _ in FEATURE_PATHS]


@dataclass
class PlayerSimilarity:
    player_id: int
    username: str
    cosine_similarity: float
    style_distance: float

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Feature extraction
# --------------------------------------------------------------------------- #
def _dig(d: dict, path: tuple):
    cur = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def extract_feature_row(features: dict | None) -> list[float | None]:
    """Pull the 22 modelling features (in canonical order) from a profile blob."""
    features = features or {}
    row: list[float | None] = []
    for _, path in FEATURE_PATHS:
        v = _dig(features, path)
        row.append(float(v) if isinstance(v, (int, float)) else None)
    return row


# --------------------------------------------------------------------------- #
# Persistence helpers
# --------------------------------------------------------------------------- #
def _ensure_dir() -> None:
    os.makedirs(MODELS_DIR, exist_ok=True)


def _path(name: str) -> str:
    return os.path.join(MODELS_DIR, name)


def _save_pickle(obj, name: str) -> None:
    _ensure_dir()
    with open(_path(name), "wb") as f:
        pickle.dump(obj, f)


def _load_pickle(name: str):
    with open(_path(name), "rb") as f:
        return pickle.load(f)


def _read_meta() -> dict:
    try:
        with open(_path("pca_meta.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"version": 0, "n_components": 0, "feature_names": [], "player_count": 0}


def _write_meta(version: int, n_components: int, player_count: int) -> None:
    _ensure_dir()
    with open(_path("pca_meta.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": version,
                "n_components": n_components,
                "feature_names": FEATURE_NAMES,
                "player_count": player_count,
            },
            f,
        )


def pca_version() -> int:
    return _read_meta().get("version", 0)


def model_exists() -> bool:
    return os.path.exists(_path("style_pca.pkl")) and os.path.exists(_path("scaler.pkl"))


# --------------------------------------------------------------------------- #
# 1. Feature matrix
# --------------------------------------------------------------------------- #
def build_feature_matrix(db) -> tuple[np.ndarray, list[int], list[str]]:
    """Build the [n_players, 22] matrix, imputing nulls with the column median.

    Also fits and persists the StandardScaler (and the medians needed to impute a
    single player at query time).
    """
    from sqlalchemy import select

    from .models import PlayerProfile

    profiles = list(db.scalars(select(PlayerProfile)))
    player_ids = [p.player_id for p in profiles]
    raw = np.array(
        [extract_feature_row(p.features) for p in profiles], dtype=object
    )

    n_features = len(FEATURE_NAMES)
    if raw.size == 0:
        raw = np.empty((0, n_features), dtype=object)

    # Column medians over present values; fall back to 0 for all-null columns.
    medians = np.zeros(n_features, dtype=np.float64)
    matrix = np.zeros((len(player_ids), n_features), dtype=np.float64)
    for j in range(n_features):
        col = [raw[i][j] for i in range(len(player_ids)) if raw[i][j] is not None]
        medians[j] = float(np.median(col)) if col else 0.0
    for i in range(len(player_ids)):
        for j in range(n_features):
            v = raw[i][j]
            matrix[i, j] = medians[j] if v is None else float(v)

    scaler = StandardScaler().fit(matrix) if len(player_ids) else StandardScaler()
    _save_pickle(scaler, "scaler.pkl")
    _save_pickle(medians, "medians.pkl")
    return matrix, player_ids, list(FEATURE_NAMES)


# --------------------------------------------------------------------------- #
# 2. PCA
# --------------------------------------------------------------------------- #
def fit_style_pca(matrix: np.ndarray, n_components: int = DEFAULT_COMPONENTS) -> PCA:
    """Fit PCA on a (scaled) matrix, persist it, and report explained variance."""
    n_samples, n_features = matrix.shape
    n = max(1, min(n_components, n_samples, n_features))

    pca = PCA(n_components=n).fit(matrix)
    evr = pca.explained_variance_ratio_
    print("PCA explained variance ratio per component:")
    for i, r in enumerate(evr):
        print(f"  PC{i + 1}: {r:.4f}")
    cumulative = float(evr.sum())
    print(f"  cumulative ({n} comps): {cumulative:.4f}")

    if cumulative <= EXPLAINED_VARIANCE_TARGET:
        warnings.warn(
            f"Cumulative explained variance {cumulative:.3f} <= "
            f"{EXPLAINED_VARIANCE_TARGET}; increasing components to {FALLBACK_COMPONENTS}.",
            stacklevel=2,
        )
        n2 = max(1, min(FALLBACK_COMPONENTS, n_samples, n_features))
        if n2 != n:
            pca = PCA(n_components=n2).fit(matrix)

    _save_pickle(pca, "style_pca.pkl")
    return pca


# --------------------------------------------------------------------------- #
# Orchestrator: fit everything + recompute all vectors
# --------------------------------------------------------------------------- #
def fit_style_embeddings(db, n_components: int | None = None) -> dict:
    """Full (re)fit: build matrix, scale, fit PCA, bump version, recompute vectors.

    Old vectors stay queryable; each player's row is overwritten as it is recomputed.
    """
    n_components = n_components or DEFAULT_COMPONENTS
    matrix, player_ids, _ = build_feature_matrix(db)
    if len(player_ids) < 2:
        raise ValueError("Need at least 2 players with profiles to fit a style PCA.")

    scaler = _load_pickle("scaler.pkl")
    scaled = scaler.transform(matrix)
    pca = fit_style_pca(scaled, n_components)

    version = _read_meta().get("version", 0) + 1
    _write_meta(version, pca.n_components_, len(player_ids))

    vectors = pca.transform(scaled)
    _store_vectors(db, player_ids, vectors, version)
    # Phase 7: a refit invalidates every cached style vector.
    try:
        from .cache import invalidate_all_style

        invalidate_all_style()
    except Exception:  # noqa: BLE001
        pass
    return {"version": version, "n_components": pca.n_components_, "players": len(player_ids)}


def _store_vectors(db, player_ids, vectors, version: int) -> None:
    from .models import PlayerStyleVector

    for pid, vec in zip(player_ids, vectors):
        row = db.get(PlayerStyleVector, pid)
        payload = [float(x) for x in vec]
        if row is None:
            db.add(PlayerStyleVector(player_id=pid, vector=payload, pca_version=version))
        else:
            row.vector = payload
            row.pca_version = version
    db.commit()


# --------------------------------------------------------------------------- #
# 3. Single-player embedding
# --------------------------------------------------------------------------- #
def compute_style_vector(player_id: int, db) -> np.ndarray:
    """Transform one player's features through the fitted scaler + PCA and store it."""
    from .models import PlayerProfile

    profile = db.get(PlayerProfile, player_id)
    if profile is None:
        raise ValueError(f"No profile for player {player_id}")
    if not model_exists():
        raise RuntimeError("Style PCA model not fitted yet.")

    medians = _load_pickle("medians.pkl")
    scaler = _load_pickle("scaler.pkl")
    pca = _load_pickle("style_pca.pkl")

    raw = extract_feature_row(profile.features)
    row = np.array(
        [medians[j] if v is None else v for j, v in enumerate(raw)], dtype=np.float64
    ).reshape(1, -1)
    vec = pca.transform(scaler.transform(row))[0]

    _store_vectors(db, [player_id], [vec], pca_version())
    return vec


# --------------------------------------------------------------------------- #
# 4. Similar players
# --------------------------------------------------------------------------- #
def _load_all_vectors(db) -> tuple[list[int], np.ndarray]:
    from sqlalchemy import select

    from .models import PlayerStyleVector

    rows = list(db.scalars(select(PlayerStyleVector)))
    ids = [r.player_id for r in rows]
    if not ids:
        return [], np.zeros((0, 0))
    mat = np.array([r.vector for r in rows], dtype=np.float64)
    return ids, mat


def _usernames(db, player_ids: list[int]) -> dict[int, str]:
    from sqlalchemy import select

    from .models import Player

    rows = db.scalars(select(Player).where(Player.id.in_(player_ids)))
    return {p.id: p.username for p in rows}


def find_similar_players(player_id: int, db, top_k: int = 5) -> list[PlayerSimilarity]:
    ids, mat = _load_all_vectors(db)
    if player_id not in ids:
        return []
    target = mat[ids.index(player_id)]
    target_norm = np.linalg.norm(target) or 1e-9

    sims: list[PlayerSimilarity] = []
    names = _usernames(db, [i for i in ids if i != player_id])
    for i, pid in enumerate(ids):
        if pid == player_id:
            continue
        vec = mat[i]
        cos = float(target @ vec / (target_norm * (np.linalg.norm(vec) or 1e-9)))
        dist = float(np.linalg.norm(target - vec))
        sims.append(
            PlayerSimilarity(
                player_id=pid,
                username=names.get(pid, str(pid)),
                cosine_similarity=round(cos, 4),
                style_distance=round(dist, 4),
            )
        )
    sims.sort(key=lambda s: s.cosine_similarity, reverse=True)
    return sims[:top_k]


# --------------------------------------------------------------------------- #
# 5. Clustering + archetypes
# --------------------------------------------------------------------------- #
ARCHETYPES = (
    "Attacker",
    "Tactician",
    "Endgame Grinder",
    "Opening Theorist",
    "Gambiteer",
    "All-Rounder",
)


def _archetype_from_zfeatures(z: dict[str, float]) -> str:
    """Pick an archetype label from a cluster centroid's standardised features."""
    def g(name: str) -> float:
        return z.get(name, 0.0)

    scores = {
        "Gambiteer": g("sacrifice_tendency") + g("aggression_index"),
        "Tactician": -g("mean_cpl") + g("tactical_opportunity_conversion") + g("brilliant_move_rate"),
        # endgame_accuracy is a CPL (higher = weaker), so weak endgame = high value.
        "Attacker": g("aggression_index") + g("endgame_accuracy"),
        "Endgame Grinder": -g("endgame_accuracy") + g("queen_trade_avoidance") + g("endgame_conversion_rate"),
        "Opening Theorist": g("opening_flexibility"),
    }
    best, best_score = max(scores.items(), key=lambda kv: kv[1])
    # A centroid near the origin (no dominant trait) is an all-rounder.
    if max(abs(v) for v in z.values()) < 0.5 or best_score < 0.5:
        return "All-Rounder"
    return best


def cluster_players(db, n_clusters: int = 6) -> dict:
    """KMeans over style vectors; label clusters and persist per-player archetypes."""
    ids, mat = _load_all_vectors(db)
    if len(ids) < 2:
        return {"clusters": {}, "assignments": {}}

    k = max(1, min(n_clusters, len(ids)))
    km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(mat)
    labels = km.labels_

    # Standardised feature centroids per cluster (for interpretable labelling).
    matrix, fids, _ = build_feature_matrix(db)
    scaler = _load_pickle("scaler.pkl")
    scaled = scaler.transform(matrix) if len(fids) else np.zeros((0, len(FEATURE_NAMES)))
    fid_index = {pid: i for i, pid in enumerate(fids)}

    clusters: dict[int, dict] = {}
    used: set[str] = set()
    for c in range(k):
        members = [ids[i] for i in range(len(ids)) if labels[i] == c]
        zrows = [scaled[fid_index[pid]] for pid in members if pid in fid_index]
        centroid = np.mean(zrows, axis=0) if zrows else np.zeros(len(FEATURE_NAMES))
        z = dict(zip(FEATURE_NAMES, centroid))
        archetype = _archetype_from_zfeatures(z)
        # Keep labels distinct where possible (fall back gracefully if collisions).
        if archetype in used and archetype != "All-Rounder":
            archetype = next((a for a in ARCHETYPES if a not in used), archetype)
        used.add(archetype)
        dominant = sorted(z.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
        clusters[c] = {
            "archetype": archetype,
            "player_ids": members,
            "dominant_features": [name for name, _ in dominant],
        }

    assignments = {ids[i]: clusters[labels[i]]["archetype"] for i in range(len(ids))}
    _store_archetypes(db, assignments)
    return {"clusters": clusters, "assignments": assignments}


def _store_archetypes(db, assignments: dict[int, str]) -> None:
    from .models import PlayerProfile

    for pid, archetype in assignments.items():
        profile = db.get(PlayerProfile, pid)
        if profile is not None:
            profile.archetype = archetype
    db.commit()


# --------------------------------------------------------------------------- #
# 6. Comparison
# --------------------------------------------------------------------------- #
def _player_vector(db, player_id: int) -> np.ndarray | None:
    from .models import PlayerStyleVector

    row = db.get(PlayerStyleVector, player_id)
    return np.array(row.vector, dtype=np.float64) if row else None


def compare_players(player_a: int, player_b: int, db) -> dict:
    va = _player_vector(db, player_a)
    vb = _player_vector(db, player_b)
    if va is None or vb is None:
        raise ValueError("Both players must have a style vector.")

    cos = float(va @ vb / ((np.linalg.norm(va) or 1e-9) * (np.linalg.norm(vb) or 1e-9)))
    dim_diff = [round(float(x), 4) for x in (va - vb)]

    # Dominant differences are reported in the interpretable raw-feature space.
    from .models import PlayerProfile

    fa = extract_feature_row(db.get(PlayerProfile, player_a).features)
    fb = extract_feature_row(db.get(PlayerProfile, player_b).features)
    diffs = []
    for name, a, b in zip(FEATURE_NAMES, fa, fb):
        if a is None or b is None:
            continue
        diffs.append({"feature": name, "player_a": round(a, 4), "player_b": round(b, 4),
                      "abs_diff": abs(a - b)})
    diffs.sort(key=lambda d: d["abs_diff"], reverse=True)
    dominant = [{k: d[k] for k in ("feature", "player_a", "player_b")} for d in diffs[:5]]

    return {
        "cosine_similarity": round(cos, 4),
        "dimension_diff": dim_diff,
        "dominant_differences": dominant,
    }


# --------------------------------------------------------------------------- #
# 7. Refit strategy
# --------------------------------------------------------------------------- #
def _player_profile_count(db) -> int:
    from sqlalchemy import func, select

    from .models import PlayerProfile

    return int(db.scalar(select(func.count()).select_from(PlayerProfile)) or 0)


def should_refit(previous_count: int, current_count: int) -> bool:
    """True if the player count crossed one of the refit thresholds."""
    return any(previous_count < t <= current_count for t in REFIT_THRESHOLDS)


def refit_if_needed(db) -> dict | None:
    """Refit when a threshold is crossed (or when no model exists yet).

    Returns the refit summary, or ``None`` if nothing was done.
    """
    current = _player_profile_count(db)
    if current < 2:
        return None
    last = _read_meta().get("player_count", 0)
    if not model_exists() or should_refit(last, current):
        return fit_style_embeddings(db)
    return None
