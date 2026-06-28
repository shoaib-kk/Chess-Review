"""Tests for the Stockfish engine pool and the engine error taxonomy.

The pool tests need a real Stockfish binary; they skip gracefully when one is not
installed so CI without the engine stays green. The error-taxonomy test for a
missing binary runs everywhere (it deliberately points at a non-existent path).
"""

from __future__ import annotations

import os
import threading
import time

import chess
import pytest

os.environ.setdefault("APP_ENV", "dev")

import stockfish_engine
from stockfish_engine import EngineUnavailableError, StockfishEngine, find_stockfish


def _stockfish_available() -> bool:
    try:
        find_stockfish()
        return True
    except EngineUnavailableError:
        return False


requires_engine = pytest.mark.skipif(
    not _stockfish_available(), reason="Stockfish binary not installed in this environment"
)


# ── error taxonomy (no engine required) ──────────────────────────────────────

def test_missing_binary_raises_engine_unavailable():
    """A non-existent path must raise the typed error, not a bare RuntimeError."""
    with pytest.raises(EngineUnavailableError):
        StockfishEngine(path=r"/definitely/not/stockfish/here").__enter__()


# ── pool behaviour (needs a real engine) ─────────────────────────────────────

@requires_engine
def test_engine_reused_across_checkouts():
    """Sequential checkouts should hand back the same underlying process."""
    path = find_stockfish()
    pool = stockfish_engine._get_pool(path)
    # Drain any idle engines so we observe a clean reuse cycle.
    with pool._lock:
        pool._idle.clear()

    with StockfishEngine() as e1:
        first = e1.engine
    with StockfishEngine() as e2:
        second = e2.engine

    assert first is second, "an idle engine should be reused, not respawned"


@requires_engine
def test_concurrency_capped_at_max_engines(monkeypatch):
    """No more than STOCKFISH_MAX_ENGINES checkouts may be live simultaneously."""
    # Build an isolated pool of size 2 so the test is independent of env config.
    path = find_stockfish()
    pool = stockfish_engine._EnginePool(path, max_engines=2)

    live = 0
    peak = 0
    peak_lock = threading.Lock()
    barrier_done = threading.Event()

    def worker():
        nonlocal live, peak
        eng = pool.acquire()
        try:
            with peak_lock:
                live += 1
                peak = max(peak, live)
            # Hold the slot briefly so workers overlap.
            time.sleep(0.2)
        finally:
            with peak_lock:
                live -= 1
            pool.release(eng)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    barrier_done.set()

    assert peak <= 2, f"pool allowed {peak} concurrent engines, expected <= 2"


@requires_engine
def test_skill_level_reset_on_return(monkeypatch):
    """A Skill Level cap set during a checkout must be reset before the engine returns."""
    path = find_stockfish()
    pool = stockfish_engine._get_pool(path)
    with pool._lock:
        pool._idle.clear()

    configured: list[dict] = []
    with StockfishEngine() as e:
        # Record every configure call on the live engine so we can prove the reset fires.
        real_configure = e.engine.configure
        monkeypatch.setattr(
            e.engine, "configure", lambda opts: (configured.append(opts), real_configure(opts))[1]
        )
        e.configure({"Skill Level": 1})
        engine_obj = e.engine

    # __exit__ must have issued a Skill Level reset (back to full strength).
    assert {"Skill Level": 20} in configured, "engine returned to pool without skill reset"
    # And the same healthy process is reused on the next checkout.
    with StockfishEngine() as e:
        assert e.engine is engine_obj


@requires_engine
def test_crashed_engine_discarded(monkeypatch):
    """An engine that raises mid-analyse is discarded, not returned to the pool."""
    path = find_stockfish()
    pool = stockfish_engine._EnginePool(path, max_engines=1)

    eng = StockfishEngine()
    eng._pool = pool
    eng.__enter__()
    checked_out = eng.engine

    # Simulate a wedged engine: make analyse raise an engine-terminated error.
    def boom(*_a, **_k):
        raise chess.engine.EngineTerminatedError("simulated crash")

    monkeypatch.setattr(checked_out, "analyse", boom)

    board = chess.Board()
    with pytest.raises(EngineUnavailableError):
        eng.analyse_position(board, depth=4)

    # The slot must have been freed (semaphore released) and the broken engine
    # must NOT be on the idle list.
    assert checked_out not in pool._idle
    # A fresh acquire should succeed (slot was freed) and give a new process.
    new_engine = pool.acquire()
    try:
        assert new_engine is not checked_out
    finally:
        pool.discard(new_engine)
