"""
Small Stockfish wrapper using python-chess.

Engine processes are expensive to start (each ``popen_uci`` spawns Stockfish and
loads its NNUE net into RAM), so we don't spawn one per use. Instead a small,
semaphore-bounded **pool** of reusable engines is shared process-wide. The public
API is unchanged — callers still write::

    with StockfishEngine(depth=...) as engine:
        engine.analyse_position(...)
        engine.analyse_candidates(...)
        engine.configure({"Skill Level": ...})

``__enter__`` checks a live engine out of the pool (blocking on a semaphore that
caps concurrency) and ``__exit__`` returns it. This means the interactive
``/analyze`` path, the background puzzle miner and ``/play/move`` can run up to N
engines concurrently instead of serialising on a single global lock, while N still
bounds peak RAM (one NNUE net per engine).
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
from pathlib import Path

import chess
import chess.engine

logger = logging.getLogger(__name__)

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")

# Memory/CPU caps for constrained hosts (e.g. Render's small instances). Stockfish
# defaults are modest, but we set them explicitly so a single analysis can't grab
# more than we budgeted. Override via env vars without a code change.
STOCKFISH_HASH_MB = int(os.getenv("STOCKFISH_HASH_MB", "32"))
STOCKFISH_THREADS = int(os.getenv("STOCKFISH_THREADS", "1"))

# Maximum number of Stockfish processes alive at once. Each holds its own NNUE net
# in RAM, so this is the knob that bounds peak memory. Default 2 keeps two analyses
# (e.g. an interactive review and the background miner, or two players) overlapping
# without OOM-killing a small host. Raise on beefier boxes via the env var.
STOCKFISH_MAX_ENGINES = max(1, int(os.getenv("STOCKFISH_MAX_ENGINES", "2")))

# Wall-clock ceiling for a single ``analyse`` call. python-chess passes this to the
# engine's transport; if Stockfish wedges (e.g. a UCI desync) we don't want it to
# permanently occupy a pool slot. On timeout we kill and discard that engine, free
# the slot, and raise ``EngineUnavailableError``. Generous default so legitimate
# deep analyses are never cut short. Override via env var.
STOCKFISH_ANALYSE_TIMEOUT_S = float(os.getenv("STOCKFISH_ANALYSE_TIMEOUT_S", "60"))


class EngineUnavailableError(RuntimeError):
    """The analysis engine could not be used for reasons unrelated to the input.

    Raised when the Stockfish binary is missing, fails to start, crashes, or an
    ``analyse`` call times out. Distinct from a ``ValueError`` (bad PGN/FEN) so the
    API can return 503 ("engine down, try again") instead of 400 ("bad input").
    """


def find_stockfish() -> str:
    project_dir = Path(__file__).resolve().parent
    local_stockfish_dir = project_dir / "stockfish"
    local_candidates = sorted(local_stockfish_dir.glob("stockfish*.exe"))

    candidates = [
        STOCKFISH_PATH,
        *local_candidates,
        shutil.which("stockfish"),
        shutil.which("stockfish.exe"),
        r"C:\Program Files\Stockfish\stockfish.exe",
        r"C:\Program Files (x86)\Stockfish\stockfish.exe",
    ]

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate

    raise EngineUnavailableError(
        "Stockfish not found. Put the engine in the stockfish folder, install it on PATH, "
        "or enter the Stockfish executable path in the sidebar."
    )


class _EnginePool:
    """A bounded pool of reusable Stockfish processes, keyed by binary path.

    A semaphore caps how many engines may be checked out (and therefore alive) at
    once; ``acquire`` blocks once that many are in use. Idle engines are kept on a
    free list so the next caller skips the ``popen_uci`` + NNUE-load cost. Engines
    that error/crash are discarded (quit, slot freed) instead of being returned, so
    a broken process never poisons a later request.
    """

    def __init__(self, path: str, max_engines: int) -> None:
        self.path = path
        self._semaphore = threading.Semaphore(max_engines)
        self._lock = threading.Lock()
        self._idle: list[chess.engine.SimpleEngine] = []

    def _new_engine(self) -> chess.engine.SimpleEngine:
        try:
            engine = chess.engine.SimpleEngine.popen_uci(self.path)
        except Exception as exc:  # binary present but won't start / handshake failed
            raise EngineUnavailableError(f"Could not start Stockfish: {exc}") from exc
        try:
            # Hash/Threads only need setting once per process. Skill Level is NOT set
            # here — it is applied per-checkout by callers and reset on return.
            engine.configure({"Hash": STOCKFISH_HASH_MB, "Threads": STOCKFISH_THREADS})
        except chess.engine.EngineError as exc:
            # Exotic builds may reject these option names; analysis still works.
            logger.warning("Could not set Hash/Threads on Stockfish: %s", exc)
        return engine

    def acquire(self) -> chess.engine.SimpleEngine:
        """Block until a slot is free, then return a live engine (reused if idle)."""
        # The semaphore both bounds concurrency and bounds the number of live
        # engines: it is only released when an engine is returned or discarded, so
        # at most ``max_engines`` ever exist.
        self._semaphore.acquire()
        try:
            with self._lock:
                engine = self._idle.pop() if self._idle else None
            if engine is None:
                engine = self._new_engine()
            return engine
        except Exception:
            # Couldn't hand back an engine — don't leak the slot.
            self._semaphore.release()
            raise

    def release(self, engine: chess.engine.SimpleEngine) -> None:
        """Return a healthy engine to the idle list and free its slot."""
        with self._lock:
            self._idle.append(engine)
        self._semaphore.release()

    def discard(self, engine: chess.engine.SimpleEngine | None) -> None:
        """Tear down a (possibly broken) engine and free its slot.

        Used when an engine raised or timed out: it might be in an undefined UCI
        state, so we never reuse it. Quitting is best-effort — the process may
        already be dead.
        """
        if engine is not None:
            try:
                engine.quit()
            except Exception:  # already dead / unresponsive — nothing to salvage
                logger.debug("Engine quit during discard failed", exc_info=True)
        self._semaphore.release()


# Pools are created lazily, one per resolved binary path (in practice always one).
_POOLS: dict[str, _EnginePool] = {}
_POOLS_LOCK = threading.Lock()


def _get_pool(path: str) -> _EnginePool:
    with _POOLS_LOCK:
        pool = _POOLS.get(path)
        if pool is None:
            pool = _EnginePool(path, STOCKFISH_MAX_ENGINES)
            _POOLS[path] = pool
        return pool


class StockfishEngine:
    def __init__(self, path: str | None = None, depth: int = 16):
        self.path = path or find_stockfish()
        self.depth = depth
        self.engine: chess.engine.SimpleEngine | None = None
        self._pool = _get_pool(self.path)
        # Set once a caller mutates Skill Level so __exit__ knows to reset it before
        # the engine goes back to the pool (otherwise a capped play engine could leak
        # into a full-strength analysis).
        self._needs_skill_reset = False

    def __enter__(self):
        # Check a live engine out of the shared pool. Blocks here if all slots are in
        # use, so concurrency is bounded without serialising everything.
        self.engine = self._pool.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        engine = self.engine
        self.engine = None
        if engine is None:
            return
        # If the body raised, the engine may be in an undefined state — discard it
        # rather than risk reusing a wedged process.
        if exc_type is not None:
            self._pool.discard(engine)
            return
        # Healthy engine: undo any per-checkout Skill Level cap before returning it,
        # so the next (possibly analysis) caller gets a full-strength engine.
        if self._needs_skill_reset:
            try:
                engine.configure({"Skill Level": 20})
            except Exception:
                # Couldn't reset — safer to discard than to leak a capped engine.
                logger.warning("Could not reset Skill Level; discarding engine", exc_info=True)
                self._pool.discard(engine)
                return
        self._pool.release(engine)

    def configure(self, options: dict) -> None:
        """Set UCI options on the running engine (e.g. {"Skill Level": 8})."""
        if self.engine is None:
            raise RuntimeError("Stockfish engine is not running.")
        # Track Skill Level so it is reset when the engine returns to the pool.
        if "Skill Level" in options:
            self._needs_skill_reset = True
        self.engine.configure(options)

    def _analyse(self, board: chess.Board, limit: chess.engine.Limit, **kwargs):
        """Run engine.analyse with a wall-clock timeout; map failures to a 503-able error.

        On timeout or any engine-level failure the engine may be wedged, so we
        discard it (the pool frees the slot) and clear ``self.engine`` to prevent
        __exit__ from double-handling it, then raise ``EngineUnavailableError``.
        """
        if self.engine is None:
            raise EngineUnavailableError("Stockfish engine is not running.")
        try:
            return self.engine.analyse(
                board, limit, timeout=STOCKFISH_ANALYSE_TIMEOUT_S, **kwargs
            )
        except (chess.engine.EngineTerminatedError, chess.engine.EngineError, TimeoutError) as exc:
            engine = self.engine
            self.engine = None
            self._pool.discard(engine)
            raise EngineUnavailableError(f"Stockfish analysis failed: {exc}") from exc

    def analyse_position(
        self,
        board: chess.Board,
        *,
        depth: int | None = None,
        movetime_ms: int | None = None,
        include_pv: bool = True,
        pv_limit: int = 8,
    ):
        limit = (
            chess.engine.Limit(time=movetime_ms / 1000)
            if movetime_ms is not None
            else chess.engine.Limit(depth=depth or self.depth)
        )
        info = self._analyse(board, limit)
        score = info["score"].pov(board.turn)
        eval_cp = score.score(mate_score=100000)

        if not include_pv:
            return eval_cp, None, []

        pv = info.get("pv", [])
        best_move = pv[0] if pv else None
        best_move_san = board.san(best_move) if best_move else None

        pv_san = []
        pv_board = board.copy()
        for move in pv[:pv_limit]:
            if move not in pv_board.legal_moves:
                break
            pv_san.append(pv_board.san(move))
            pv_board.push(move)

        return eval_cp, best_move_san, pv_san

    def analyse_candidates(
        self,
        board: chess.Board,
        *,
        depth: int | None = None,
        multipv: int = 3,
        pv_limit: int = 8,
    ) -> list[dict]:
        """Return up to ``multipv`` candidate lines, strongest first.

        Each entry: ``{"move": san, "eval": cp, "pv": [san, ...]}`` where ``eval``
        is centipawns from the side-to-move's POV (mate encoded as ±100000) and
        ``move`` is the first move of that line. Used both to surface the top few
        engine choices to the player and to judge how forced a position was (the
        gap between the best and second-best lines).
        """
        limit = chess.engine.Limit(depth=depth or self.depth)
        infos = self._analyse(board, limit, multipv=max(1, multipv))
        # With multipv python-chess returns a list; guard against builds that
        # still hand back a single dict.
        if isinstance(infos, dict):
            infos = [infos]

        candidates: list[dict] = []
        for info in infos:
            pv = info.get("pv", [])
            if not pv:
                continue
            score = info["score"].pov(board.turn)
            eval_cp = score.score(mate_score=100000)

            pv_san: list[str] = []
            pv_board = board.copy()
            for move in pv[:pv_limit]:
                if move not in pv_board.legal_moves:
                    break
                pv_san.append(pv_board.san(move))
                pv_board.push(move)

            candidates.append(
                {
                    "move": board.san(pv[0]),
                    "eval": eval_cp,
                    "pv": pv_san,
                }
            )
        return candidates
