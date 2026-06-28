from __future__ import annotations

import logging
import sys
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .auth import current_device
from .db import SessionLocal, wait_for_db
from .repositories.games import save_reviewed_game
from .schemas import (
    AnalyzeRequest,
    ChessComAnalyzeRequest,
    ChessComGameResponse,
    GameSummaryResponse,
    HealthResponse,
)
from .serializers import serialize_game_summary
from .services.chesscom_client import ChessComClientError, get_recent_games
from .services.opening_repertoire import get_opening_repertoire
from .services.player_insights import get_player_insights
from .services.rate_limit import analyze_rate_limiter, lookup_rate_limiter
from .routers.puzzles import router as puzzles_router
from .routers.play import router as play_router
from .routers.drills import router as drills_router
from .routers.daily import router as daily_router
from .routers.training import router as training_router

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from services.game_analyzer import analyze_pgn
except ModuleNotFoundError:
    from game_analyzer import analyze_pgn

from stockfish_engine import EngineUnavailableError


app = FastAPI(title="Chessspy API", version="1.0.0")
app.include_router(puzzles_router)
app.include_router(play_router)
app.include_router(drills_router)
app.include_router(daily_router)
app.include_router(training_router)


@app.on_event("startup")
def _startup() -> None:
    # Block until Postgres is reachable so requests aren't served against a DB
    # that hasn't finished starting. Migrations are applied by the entrypoint.
    wait_for_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://chess-review-kappa.vercel.app",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5177",
        "http://127.0.0.1:5177",
        # DigitalOcean droplet (frontend is served same-origin via nginx, so CORS
        # isn't normally exercised; listed for direct API access / safety).
        "http://170.64.177.231:8080",
    ],
    # Covers Vercel preview deployments (e.g. chess-review-git-<branch>-<user>.vercel.app)
    # while forbidding extra dotted segments so a host like chess-review.evil.com
    # or chess-review-x.attacker.vercel.app can't match.
    allow_origin_regex=r"https://chess-review(-[a-z0-9-]+)?\.vercel\.app",
    # No cookies/auth are used, so credentialed requests aren't needed.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/")
def root_health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=GameSummaryResponse, dependencies=[Depends(analyze_rate_limiter)])
def analyze(request: AnalyzeRequest, device: str = Depends(current_device)) -> dict:
    # Pasted PGN: no Chess.com identity, so no color detection. Owned by device.
    try:
        return _run_analysis(request.pgn, request.depth, request.mode, owner_id=device, player_username="")
    except EngineUnavailableError:
        # Engine missing / crashed / timed out — not the user's PGN. Tell them to retry.
        logger.exception("Analysis engine unavailable")
        raise HTTPException(status_code=503, detail="Analysis engine temporarily unavailable. Please try again shortly.")
    except Exception:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=400, detail="Could not analyze this game. Check the PGN and try again.")


@app.get("/chesscom/{username}/games", response_model=list[ChessComGameResponse], dependencies=[Depends(lookup_rate_limiter)])
def chesscom_games(username: str, limit: int = Query(default=20, ge=1, le=50)) -> list[dict]:
    try:
        return get_recent_games(username, limit=limit)
    except ChessComClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/player-insights/{username}", dependencies=[Depends(lookup_rate_limiter)])
def player_insights(
    username: str,
    limit: int = Query(default=200, ge=1, le=300),
    time_class: str | None = Query(default=None, pattern="^(rapid|blitz|bullet)$"),
    rated_only: bool = Query(default=False),
) -> dict:
    try:
        return get_player_insights(
            username=username,
            limit=limit,
            time_class=time_class,
            rated_only=rated_only,
        )
    except ChessComClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/opening-repertoire/{username}", dependencies=[Depends(lookup_rate_limiter)])
def opening_repertoire(
    username: str,
    limit: int = Query(default=500, ge=1, le=500),
    time_class: str | None = Query(default=None, pattern="^(rapid|blitz|bullet)$"),
    rated_only: bool = Query(default=False),
) -> dict:
    try:
        return get_opening_repertoire(
            username=username,
            limit=limit,
            time_class=time_class,
            rated_only=rated_only,
        )
    except ChessComClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/chesscom/analyze", response_model=GameSummaryResponse, dependencies=[Depends(analyze_rate_limiter)])
def chesscom_analyze(request: ChessComAnalyzeRequest, device: str = Depends(current_device)) -> dict:
    # The game is owned by the device; request.username is the Chess.com player
    # used for color/accuracy detection only.
    try:
        return _run_analysis(
            request.pgn, request.depth, request.mode, owner_id=device, player_username=request.username.strip()
        )
    except EngineUnavailableError:
        logger.exception("Analysis engine unavailable")
        raise HTTPException(status_code=503, detail="Analysis engine temporarily unavailable. Please try again shortly.")
    except Exception:
        logger.exception("Chess.com analysis failed")
        raise HTTPException(status_code=400, detail="Could not analyze this game. Check the PGN and try again.")


@lru_cache(maxsize=32)
def _cached_analysis(pgn: str, depth: int, mode: str):
    """Cache the expensive Stockfish pass, keyed only by the inputs that affect
    it. Serialization (which depends on the player) and per-device persistence
    are done per request below, so the same game isn't re-analysed per device."""
    return analyze_pgn(pgn_text=pgn, depth=depth, mode=mode)


def _run_analysis(pgn: str, depth: int, mode: str, *, owner_id: str, player_username: str) -> dict:
    summary = _cached_analysis(pgn, depth, mode)
    # serialize_game_summary builds a fresh dict and never mutates the cached
    # summary, so no defensive copy is needed.
    serialized = serialize_game_summary(summary, username=player_username or None)
    # Persist every reviewed game, scoped to the device (idempotent dedup on
    # owner_id + url/PGN hash). Best-effort: never let a DB hiccup break review.
    try:
        with SessionLocal() as session:
            save_reviewed_game(
                session,
                owner_id=owner_id,
                username=player_username or None,
                pgn=pgn,
                summary=summary,
                analysis_json=serialized,
                depth=depth,
                mode=mode,
            )
    except Exception:  # pragma: no cover - persistence is best-effort
        logger.warning("Failed to persist reviewed game", exc_info=True)
    return serialized
