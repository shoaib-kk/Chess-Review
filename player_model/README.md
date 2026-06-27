# Player Modelling Engine — PGN Ingestion Pipeline

A self-contained background pipeline that ingests PGN files, runs Stockfish
analysis on each relevant position, and stores the **raw** per-position results
for a later feature-extraction phase. It is intentionally isolated from the main
review app (which uses Postgres) — this package has its own SQLite database,
Celery worker and Redis queue.

## Components

| File | Responsibility |
|------|----------------|
| `config.py` | Env-driven configuration (`STOCKFISH_DEPTH`, DB/Redis URLs, thresholds). |
| `db.py` | SQLAlchemy engine, session factory, `Base`, `init_db()`. |
| `models.py` | ORM models: `players`, `games`, `positions`, `ingestion_jobs`, `player_profiles`. |
| `pgn_ingest.py` | Splits a multi-game PGN and extracts per-game / per-move data. |
| `analyzer.py` | Per-position Stockfish analysis (top-3 multipv, CPL, classification). |
| `engine.py` | **One Stockfish instance per worker process** + crash recovery. |
| `repository.py` | All SQL: players/games/jobs/positions, dedup, resume marker. |
| `tasks.py` | The Celery ingestion task (batched writes, progress, resume). |
| `features.py` | **Phase 2** feature extractor — one function per feature group + orchestrator. |
| `profile_tasks.py` | Celery task that builds a profile when ingestion completes. |
| `patterns.py` | **Phase 3** behavioural pattern detectors + confidence scoring + orchestrator. |
| `pattern_tasks.py` | Celery task that detects patterns after a profile is computed. |
| `twin.py` | **Phase 4** digital-twin move selection (candidates, scoring, softmax, overrides, backtest) + Phase 5 similarity prior. |
| `encoding.py` | **Phase 5** 68-dim position feature encoder. |
| `index_manager.py` | **Phase 5** FAISS index build / incremental add / on-demand LRU load / search. |
| `benchmark_index.py` | **Phase 5** build + query benchmark for 10k/50k/100k positions. |
| `celery_app.py` | Celery app + worker lifecycle hooks. |
| `api.py` | FastAPI: ingest/status/profile/patterns + `POST /twin/{id}/move`, `POST /twin/{id}/backtest`, `GET /players/{id}/similar`. |

## Phase 2 — player feature extraction

`features.py` turns the raw Phase 1 positions into a structured player profile
(stored as a JSON blob in `player_profiles`, keyed by `player_id`). It performs
**no new Stockfish calls** — every feature comes from stored data or cheap
python-chess computation on the stored FENs.

Feature groups (one function each): `accuracy_features`, `tactical_features`,
`positional_features`, `endgame_features`, `style_features`, `opening_features`,
`time_features`. `compute_player_profile(player_id, db)` calls them all, assembles
the dict and upserts the `player_profiles` row (updating `computed_at`).

Key behaviours:
- **Triggered automatically** — `tasks.ingest_pgn` enqueues `profile_tasks.compute_profile`
  the moment a job reaches `completed`.
- **Graceful degradation** — statistical features return `null` when fewer than
  `MIN_SAMPLES` (10) data points exist; occurrence ratios return `null` on a zero
  denominator.
- **Sampled mobility** — `piece_activity_index` samples every 5th position so it
  never fans out to O(n) work.
- **Deterministic** — ordering, slicing and `statistics` give identical output for
  identical input rows.
- **Two raw columns added to `positions`** (`clock_seconds`, `candidate_evals`) so
  the time and complexity features have their inputs; both are nullable, so
  pre-existing rows simply degrade to `null`.

```bash
curl http://localhost:8000/players/1/profile     # -> {player_id, computed_at, game_count, features{...}}
```

## Phase 3 — behavioural pattern detection

`patterns.py` discovers *recurring* mistakes from a player's history and stores
them in `behavioural_patterns` (one row per pattern). Like Phase 2 it makes **no
new Stockfish calls** — detection is stored data + python-chess board analysis.

Detectors (each emits human-readable, UI-ready labels):
- `detect_hanging_piece_patterns` — repeated `(piece, phase)` blunders left en prise.
- `detect_endgame_weakness` — pawn/rook/queen endgames where CPL > 1.4× overall.
- `detect_tactical_blindness` — missed forks / pins / back-rank / hanging-piece tactics
  (motif classified from the position with python-chess).
- `detect_avoidance_behaviours` — declining ≥60% of available queen/rook/bishop trades.
- `detect_overextension` — kingside pawn storms that collapse into weaknesses.

`compute_behavioural_patterns(player_id, db)` runs them all, deduplicates by
`pattern_type` (keeping the strongest by severity × confidence), persists and
returns the list. It is auto-triggered by `pattern_tasks.compute_patterns` once
`compute_profile` finishes.

**Confidence** = `min(sample_count/10, 1) * (1 - p_value)`, where `p_value` comes
from a one-sided `scipy.stats.binomtest` against the player's baseline blunder
rate. Patterns below `0.5` confidence, or for players with fewer than 3 games,
are suppressed. (Note: by construction a pattern needs ≈6+ recurrences to clear
0.5, since `sample_count/10` caps the score.)

```bash
curl http://localhost:8000/players/1/patterns   # sorted by severity_score * confidence DESC
```

## Phase 4 — digital twin move selection

`twin.py` generates the move a *specific* player would most characteristically
play. One Stockfish call per request produces the top-N candidates; everything
after that is pure Python.

- `get_candidates(fen, n, depth)` — single engine call; computes the boolean flags
  (`involves_tactic`, `is_sacrifice`, `is_trade`, `is_aggressive`, `piece_moved`)
  from the position using a static-exchange evaluation and python-chess.
- `score_candidate` = `eval + tactic + sacrifice + aggression + trade` weights,
  each implemented exactly per spec. The stored Phase 2 blob is adapted onto the
  flat 0-1 `ProfileView` the formulas expect (e.g. `aggression_index`, a centipawn
  magnitude, is normalised to 0-1).
- `softmax(scores, T)` with a player-derived, bounded temperature
  (`0.3 ≤ T ≤ 2.0`) from `accuracy_variance_across_games`.
- `apply_pattern_overrides` — queen-trade avoidance, tactical-blindness damping of
  the top candidate, and sacrifice boosting; renormalised after each.
- `select_twin_move(fen, player_id, db)` samples the final move;
  `backtest_twin(player_id, pgn, db)` replays a game and reports
  `move_match_rate`, `top3_match_rate`, `cpl_correlation`, `style_match_score`.

```bash
curl -X POST http://localhost:8000/twin/1/move     -d '{"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}'
# -> {"move": "e2e4", "confidence": 0.41}
curl -X POST http://localhost:8000/twin/1/backtest -d '{"game_pgn": "1. e4 e5 ..."}'
```

The engine is the single per-worker Stockfish from `engine.py`; twin calls take a
process lock since `SimpleEngine` is not thread-safe.

## Phase 5 — position similarity search

When the twin reaches a position with no close historical match, it borrows the
player's decisions from the most similar positions they've actually played.

- `encoding.encode_position(fen)` → a 68-dim float32 vector (material, pawn
  structure, king safety, mobility, eval context, control, castling/structure,
  threats). Every component — including the evaluation context — is derived
  deterministically from the FEN, so index and query encodings are homogeneous.
- `index_manager` builds a per-player **FAISS `IndexFlatL2`** stored on disk under
  `PM_INDEX_DIR` (default `/data/indices`), with row-aligned `{id}_moves.json` and a
  `{id}_meta.json` carrying the index `version` + the profile version. Indices load
  on demand through a 20-player LRU cache that self-invalidates on the meta version.
  `build_position_index`, `add_positions_to_index` (incremental) and
  `find_similar_positions` are the entry points.
- The index is (re)built automatically after Phase 2 profile computation.
- **Similarity prior** (in `twin.decide_twin_move`): when the closest neighbour is
  within distance `0.15`, a move distribution over the top-5 neighbours weighted by
  `1/distance` is blended as `0.6 * model + 0.4 * similarity`; otherwise the model
  distribution is used unchanged (the Phase 4 fallback).

```bash
curl "http://localhost:8000/players/1/similar?fen=<FEN>&k=5"
python -m player_model.benchmark_index            # 10k/50k/100k build + query timings
```

Measured on this machine: 50k positions build in ~22s (budget < 30s) and queries
return in ~2ms (budget < 50ms).

## Section 1 — Chess.com sync

Beyond PGN upload, a player can connect a Chess.com account and have their games
fetched and analysed automatically.

- `chesscom_client.py` — thin client over `api.chess.com/pub`: lists monthly
  archives, normalises games, and exposes the player's public profile (avatar).
  Filtering policy lives here: **daily** games and non-standard variants are
  excluded; **bullet** is kept but tagged (`Game.time_class`) so it can be
  weighted/queried separately.
- `sync_tasks.py` — the Celery task `sync_chess_com`: lists archives → filters →
  **dedups by `chess_com_game_url`** → analyses each new game's positions with the
  same per-position pipeline as PGN upload → advances the per-player incremental
  watermark (`last_game_end_time`) → recomputes the profile. A second task,
  `enqueue_incremental_syncs`, is scheduled by **Celery beat** every
  `PM_SYNC_INTERVAL_HOURS` (default 6) to resync every connected player.
- New columns: `players.chess_com_username / avatar_url / last_synced_at /
  last_game_end_time` and `games.source / chess_com_game_url / time_class /
  end_time`, all nullable/additive (`init_db` upgrades existing SQLite DBs in
  place).

```bash
curl http://localhost:8000/chess-com/hikaru/profile -H "X-API-Key: $KEY"   # avatar step
curl -X POST http://localhost:8000/players/1/connect-chess-com \
     -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"chess_com_username": "hikaru", "time_classes": ["blitz","rapid"]}'
curl http://localhost:8000/players/1/sync-status -H "X-API-Key: $KEY"
```

## Frontend (Section 8)

The three player-modelling surfaces live in the main app at
`frontend/src/playerModel/` and are reached from the **Player Twin** sidebar item:

- `Onboarding.tsx` — username + time-control picker → avatar confirmation → live
  sync progress (polling) → archetype + top-patterns reveal with CTAs.
- `ProfileDashboard.tsx` — header, style radar, accuracy-by-phase, behavioural
  pattern cards, ECO opening treemap, and a weakness heatmap on a board.
- `TwinGameplay.tsx` — interactive board + personality panel + move history, a
  600–1200 ms thinking delay, Stockfish-less random fallback on engine error, and
  a post-game modal (move-match rate + least-confident "key moment").

`api.ts` talks to the engine via `VITE_PM_API_BASE_URL` (default
`http://127.0.0.1:8000`) with `VITE_PM_API_KEY`; `types.ts` mirrors every
response shape.

### Tests

```bash
pytest player_model/tests/                          # or, with no pytest installed:
python -m player_model.tests.test_features
python -m player_model.tests.test_patterns
python -m player_model.tests.test_twin
python -m player_model.tests.test_encoding
python -m player_model.tests.test_index
```
`test_features.py` covers every feature group; `test_patterns.py` covers every
detector plus the global gates and an orchestrator test; `test_twin.py` verifies
each weight function in isolation, the softmax/temperature/override logic and the
SEE-based flags, and runs an engine-backed integration test through 10 moves of a
real game plus a backtest (both auto-skip if Stockfish is unavailable);
`test_encoding.py` checks the 68-dim vector's shape/range/determinism;
`test_index.py` covers FAISS build/search/incremental-add, LRU reload and the
similarity prior. All use a temporary SQLite database and need no running services.

## How it satisfies the constraints

- **One Stockfish per worker** — a module-level singleton in `engine.py`, launched
  lazily and reused across tasks/positions; compose runs the worker with
  `--concurrency=1`.
- **Skip opponent positions** — `tasks._analyse_game` only analyses plies where
  `move.turn == game.color_played` (the target player's moves).
- **Integer centipawns** — evals are converted with `mate_score` and stored as
  `Integer` columns; never floats.
- **Configurable depth** — `STOCKFISH_DEPTH` (default 18).
- **Raw data only** — no aggregation/feature computation here; positions store the
  per-move primitives only.
- **Batched writes** — positions flush every `PM_BATCH_SIZE` (default 50) rows.
- **Resume from last saved ply** — each game tracks `last_analysed_ply`; on a crash
  or retry the worker queries `max_saved_ply()` and skips already-saved plies.
  Stockfish crashes (`EngineTerminatedError`) relaunch the engine in-place, and the
  Celery task also retries with `acks_late` so an in-flight job is never lost.

## Run it

```bash
# From the repo root
docker compose -f player_model/docker-compose.yml up --build
```

This starts Redis, the FastAPI service on `:8000`, and a Celery worker (with
Stockfish installed in the image).

### Submit a PGN

```bash
curl -F "username=hikaru" -F "file=@games.pgn" http://localhost:8000/ingest
# -> {"job_id": 1, "player_id": 1, "status": "pending"}

curl http://localhost:8000/ingest/1/status
# -> {"job_id":1,"status":"running","total_games":40,"processed_games":12,...}
```

### Run locally — no Docker, Redis or Celery worker (recommended)

For a laptop, the engine can run as a **single process**. With `PM_INLINE_TASKS`
on (the default), the API runs background jobs (Chess.com sync, profile/pattern
computation, FAISS index build) in an in-process worker thread instead of
shipping them to a Celery worker over Redis — so the twin becomes playable with
just one command:

```bash
python -m player_model.run_local        # -> http://127.0.0.1:8000
```

This launcher sets laptop-friendly defaults (project-local SQLite DB and
`player_model_data/` artifact dir, CORS for the Vite dev server, master key
`dev-master-key`) and finds Stockfish automatically from the bundled
`stockfish/` directory, `STOCKFISH_PATH` or PATH. See `runner.py` for how inline
dispatch works; `SimpleEngine` access is serialised through `engine.ENGINE_LOCK`
so an inline ingestion and a twin-move request never use Stockfish at once.

**Whole feature in one shot (Windows):** from the repo root run
`powershell -ExecutionPolicy Bypass -File .\run_player_twin.ps1` to start both
the engine and the Vite frontend, then open <http://localhost:5173> and click the
**Player Twin** tab.

### Run locally with a real Celery worker + Redis

Set `PM_INLINE_TASKS=0` to restore the broker/worker topology (what Docker
Compose uses):

```bash
pip install -r player_model/requirements.txt
export STOCKFISH_PATH=/path/to/stockfish    # or place it on PATH
export PM_INLINE_TASKS=0
# terminal 1: Redis (docker run -p 6379:6379 redis:7-alpine)
# terminal 2:
celery -A player_model.celery_app:celery_app worker --loglevel=info --concurrency=1
# terminal 3 (optional: 6-hourly incremental Chess.com resync):
celery -A player_model.celery_app:celery_app beat --loglevel=info
# terminal 4:
uvicorn player_model.api:app --reload --port 8000
```

## Data model notes

`positions` stores one row per analysed ply with the FEN *before* the move, the
move played (UCI), the engine's best move, `eval_before` / `eval_after` (mover
POV, integer cp), `cpl`, the `is_mistake` / `is_blunder` / `is_brilliant` flags
and `depth_used`. Classification thresholds (centipawn loss): inaccuracy `>50`,
mistake `>100`, blunder `>200`; "brilliant" flags an engine-best move that
sacrifices material while keeping the position from losing.

## Smoke test

```bash
STOCKFISH_PATH=/path/to/stockfish python -m player_model._smoke_test
```
Parses a sample PGN, exercises the DB layer + dedup, and runs a real (low-depth)
Stockfish analysis end-to-end.
