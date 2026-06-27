from __future__ import annotations

import logging
import sys
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .db import SessionLocal, wait_for_db
from .repositories.games import save_reviewed_game
from .schemas import AnalyzeRequest, ChessComAnalyzeRequest, ChessComGameResponse, GameSummaryResponse, HealthResponse
from .serializers import serialize_game_summary
from .services.chesscom_client import ChessComClientError, get_recent_games
from .services.opening_repertoire import get_opening_repertoire
from .services.player_insights import get_player_insights
from .services.rate_limit import analyze_rate_limiter, lookup_rate_limiter
from .routers.puzzles import router as puzzles_router
from .routers.play import router as play_router

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from services.game_analyzer import analyze_pgn
except ModuleNotFoundError:
    from game_analyzer import analyze_pgn


app = FastAPI(title="Chess Game Reviewer API", version="1.0.0")
app.include_router(puzzles_router)
app.include_router(play_router)


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
    # Covers Vercel preview deployments (e.g. chess-review-git-<branch>-<user>.vercel.app).
    allow_origin_regex=r"https://chess-review.*\.vercel\.app",
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
def analyze(request: AnalyzeRequest) -> dict:
    try:
        return _run_cached_analysis(request.pgn, request.depth, request.mode, "")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
def chesscom_analyze(request: ChessComAnalyzeRequest) -> dict:
    try:
        return _run_cached_analysis(request.pgn, request.depth, request.mode, request.username.strip())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _run_cached_analysis(pgn: str, depth: int, mode: str, username: str) -> dict:
    return deepcopy(_cached_analysis_result(pgn, depth, mode, username))


@lru_cache(maxsize=32)
def _cached_analysis_result(pgn: str, depth: int, mode: str, username: str) -> dict:
    summary = analyze_pgn(pgn_text=pgn, depth=depth, mode=mode)
    serialized = serialize_game_summary(summary, username=username or None)
    # Persist every reviewed game (idempotent dedup by PGN hash). Runs once per
    # unique input thanks to the lru_cache; never let a DB hiccup break review.
    try:
        with SessionLocal() as session:
            save_reviewed_game(
                session,
                username=username or None,
                pgn=pgn,
                summary=summary,
                analysis_json=serialized,
                depth=depth,
                mode=mode,
            )
    except Exception:  # pragma: no cover - persistence is best-effort
        logger.warning("Failed to persist reviewed game", exc_info=True)
    return serialized
