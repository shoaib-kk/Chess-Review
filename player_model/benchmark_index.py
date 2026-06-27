"""Benchmark FAISS index build + query time for 10k / 50k / 100k positions.

Measures the raw encode+build pipeline and average single-query latency, so it is
independent of the database. Run:

    python -m player_model.benchmark_index
    python -m player_model.benchmark_index 10000 50000        # custom sizes
"""

from __future__ import annotations

import random
import sys
import time

import chess
import faiss
import numpy as np

from .encoding import VECTOR_DIM, encode_position


def _generate_fens(n: int, seed: int = 0) -> list[str]:
    """Generate ``n`` varied FENs via random legal playouts."""
    rng = random.Random(seed)
    fens: list[str] = []
    board = chess.Board()
    while len(fens) < n:
        if board.is_game_over() or board.fullmove_number > 60:
            board = chess.Board()
        moves = list(board.legal_moves)
        board.push(rng.choice(moves))
        fens.append(board.fen())
    return fens


def _bench(n: int) -> dict:
    fens = _generate_fens(n)

    t0 = time.perf_counter()
    vectors = np.vstack([encode_position(f) for f in fens]).astype(np.float32)
    index = faiss.IndexFlatL2(VECTOR_DIM)
    index.add(vectors)
    build_s = time.perf_counter() - t0

    rng = random.Random(123)
    query_fens = [rng.choice(fens) for _ in range(200)]
    queries = np.vstack([encode_position(f) for f in query_fens]).astype(np.float32)

    t0 = time.perf_counter()
    for i in range(len(query_fens)):
        index.search(queries[i : i + 1], 10)
    query_ms = (time.perf_counter() - t0) / len(query_fens) * 1000

    return {"n": n, "build_s": build_s, "query_ms": query_ms}


def main(sizes: list[int]) -> None:
    print(f"{'positions':>10} | {'build (s)':>10} | {'avg query (ms)':>15}")
    print("-" * 42)
    for n in sizes:
        r = _bench(n)
        flag = "" if r["build_s"] < 30 and r["query_ms"] < 50 else "  <-- over budget"
        print(f"{r['n']:>10} | {r['build_s']:>10.2f} | {r['query_ms']:>15.3f}{flag}")
    print("\nBudgets: build < 30s for 50k positions, query < 50ms.")


if __name__ == "__main__":
    sizes = [int(a) for a in sys.argv[1:]] or [10_000, 50_000, 100_000]
    main(sizes)
