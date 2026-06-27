"""Scatter-plot the first two PCA style dimensions, coloured by archetype.

Reads the stored style vectors and per-player archetypes from the DB and writes a
PNG. Run:

    python -m player_model.style_visualize                 # -> <PM_MODELS_DIR>/style_scatter.png
    python -m player_model.style_visualize out.png
"""

from __future__ import annotations

import os
import sys

import matplotlib

matplotlib.use("Agg")  # headless / server-safe backend
import matplotlib.pyplot as plt  # noqa: E402

from .db import SessionLocal  # noqa: E402
from .models import PlayerProfile, PlayerStyleVector  # noqa: E402
from .style_embedding import MODELS_DIR  # noqa: E402


def plot_style_scatter(output_path: str | None = None) -> str:
    output_path = output_path or os.path.join(MODELS_DIR, "style_scatter.png")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    db = SessionLocal()
    try:
        rows = db.query(PlayerStyleVector).all()
        points = []
        for r in rows:
            if len(r.vector) < 2:
                continue
            profile = db.get(PlayerProfile, r.player_id)
            archetype = (profile.archetype if profile else None) or "Unlabelled"
            points.append((r.vector[0], r.vector[1], archetype))
    finally:
        db.close()

    if not points:
        raise RuntimeError("No style vectors found — fit the style embeddings first.")

    by_arch: dict[str, list[tuple[float, float]]] = {}
    for x, y, arch in points:
        by_arch.setdefault(arch, []).append((x, y))

    fig, ax = plt.subplots(figsize=(9, 7))
    cmap = plt.get_cmap("tab10")
    for i, (arch, pts) in enumerate(sorted(by_arch.items())):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.scatter(xs, ys, label=arch, color=cmap(i % 10), s=40, alpha=0.8, edgecolors="k", linewidths=0.3)

    ax.set_xlabel("PCA dimension 1")
    ax.set_ylabel("PCA dimension 2")
    ax.set_title("Player style space (first two PCA dimensions)")
    ax.legend(title="Archetype", loc="best", fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)
    return output_path


if __name__ == "__main__":
    out = plot_style_scatter(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"Wrote {out}")
