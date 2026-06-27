"""Hardened FastAPI application for the Player Modelling Engine (Phase 7).

Adds the full route contract, a uniform response envelope, API-key auth, Redis
caching, rate limiting, structured error handling and health/metrics — without
removing the routes from earlier phases (legacy aliases are kept).
"""

from __future__ import annotations

import hashlib
import logging
import os

import chess
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, Header, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import cache, repository as repo
from .api_common import (
    ApiError,
    ErrorCode,
    MIN_GAMES_FOR_PROFILE,
    build_meta,
    error_envelope,
    success_envelope,
)
from .auth import authenticate
from .db import SessionLocal, engine, init_db
from .models import (
    BehaviouralPattern,
    Game,
    IngestionJob,
    JobStatus,
    Player,
    PlayerProfile,
    PlayerStyleVector,
)
from .chesscom_client import ChessComClientError, get_player_profile
from .runner import dispatch
from .style_embedding import compare_players, find_similar_players, pca_version
from .sync_tasks import sync_chess_com
from .tasks import ingest_pgn
from .twin import backtest_twin, decide_for_player

logger = logging.getLogger(__name__)

FRONTEND_URLS = [
    u.strip()
    for u in os.getenv("FRONTEND_URL", "http://localhost:5173").split(",")
    if u.strip()
]


# --------------------------------------------------------------------------- #
# App, rate limiting, CORS
# --------------------------------------------------------------------------- #
def _rate_key(request: Request) -> str:
    return request.headers.get("X-API-Key") or get_remote_address(request)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    init_db()
    yield


limiter = Limiter(key_func=_rate_key, default_limits=["100/minute"])
app = FastAPI(title="Player Modelling Engine API", version="1.0", lifespan=_lifespan)
# Also create the schema at import time so the app is usable whether started via
# uvicorn (lifespan) or wrapped in a bare TestClient (no lifespan). Idempotent.
init_db()
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_URLS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
):
    return authenticate(db, x_api_key)


# --------------------------------------------------------------------------- #
# Exception handlers (always envelope)
# --------------------------------------------------------------------------- #
@app.exception_handler(ApiError)
async def _api_error_handler(_request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(exc.code, exc.message),
    )


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(_request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content=error_envelope(ErrorCode.RATE_LIMITED, f"Rate limit exceeded: {exc.detail}"),
    )


@app.exception_handler(Exception)
async def _unhandled_handler(_request: Request, exc: Exception):  # pragma: no cover
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content=error_envelope("INTERNAL_ERROR", str(exc)),
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _player_or_404(db: Session, player_id: int) -> Player:
    player = db.get(Player, player_id)
    if player is None:
        raise ApiError(ErrorCode.PLAYER_NOT_FOUND, f"Player {player_id} not found.")
    return player


def _game_count(db: Session, player_id: int) -> int:
    return int(
        db.scalar(select(func.count()).select_from(Game).where(Game.player_id == player_id))
        or 0
    )


def _validate_fen(fen: str) -> None:
    try:
        chess.Board(fen)
    except ValueError:
        raise ApiError(ErrorCode.INVALID_FEN, "Invalid FEN string.")


def _fen_hash(fen: str) -> str:
    return hashlib.sha256(fen.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Cached payload builders ({"data", "meta"})
# --------------------------------------------------------------------------- #
@cache.cached(lambda player_id, db: f"profile:{player_id}:{_profile_version(db, player_id)}", cache.TTL_PROFILE)
def _profile_payload(player_id: int, db: Session) -> dict:
    profile = db.get(PlayerProfile, player_id)
    if profile is None:
        raise ApiError(ErrorCode.PROFILE_NOT_READY, "Profile not computed yet.")
    if profile.game_count < MIN_GAMES_FOR_PROFILE:
        raise ApiError(
            ErrorCode.INSUFFICIENT_GAMES,
            f"Need at least {MIN_GAMES_FOR_PROFILE} games (have {profile.game_count}).",
        )
    return {
        "data": {"features": profile.features, "archetype": profile.archetype},
        "meta": build_meta(profile.computed_at, None, profile.game_count),
    }


def _profile_version(db: Session, player_id: int) -> str:
    profile = db.get(PlayerProfile, player_id)
    return profile.computed_at.isoformat() if profile and profile.computed_at else "none"


@cache.cached(lambda player_id, db: f"patterns:{player_id}", cache.TTL_PATTERNS)
def _patterns_payload(player_id: int, db: Session) -> dict:
    rows = db.scalars(
        select(BehaviouralPattern).where(BehaviouralPattern.player_id == player_id)
    ).all()
    rows.sort(key=lambda p: p.severity_score * p.confidence, reverse=True)
    data = [
        {
            "pattern_type": p.pattern_type,
            "label": p.label,
            "description": p.description,
            "severity_score": p.severity_score,
            "frequency_score": p.frequency_score,
            "confidence": p.confidence,
            "sample_count": p.sample_count,
            "supporting_game_ids": p.supporting_game_ids,
        }
        for p in rows
    ]
    return {"data": data, "meta": build_meta(game_count=_game_count(db, player_id))}


@cache.cached(lambda player_id, db: f"style:{player_id}:{pca_version()}", cache.TTL_STYLE)
def _style_payload(player_id: int, db: Session) -> dict:
    row = db.get(PlayerStyleVector, player_id)
    if row is None:
        raise ApiError(ErrorCode.PROFILE_NOT_READY, "Style vector not computed yet.")
    profile = db.get(PlayerProfile, player_id)
    similar = [s.to_dict() for s in find_similar_players(player_id, db, top_k=5)]
    return {
        "data": {
            "vector": row.vector,
            "archetype": profile.archetype if profile else None,
            "similar_players": similar,
        },
        "meta": build_meta(row.computed_at, row.pca_version,
                           profile.game_count if profile else None),
    }


@cache.cached(lambda player_id, db: f"similar:{player_id}", cache.TTL_SIMILAR_PLAYERS)
def _similar_players_payload(player_id: int, db: Session) -> dict:
    data = [s.to_dict() for s in find_similar_players(player_id, db, top_k=5)]
    return {"data": data, "meta": build_meta(model_version=pca_version())}


@cache.cached(
    lambda player_id, fen, db: f"twin_move:{player_id}:{_fen_hash(fen)}", cache.TTL_TWIN_MOVE
)
def _twin_move_payload(player_id: int, fen: str, db: Session) -> dict:
    try:
        decision = decide_for_player(fen, player_id, db)
    except FileNotFoundError as exc:
        raise ApiError(ErrorCode.STOCKFISH_ERROR, f"Stockfish unavailable: {exc}")
    except RuntimeError as exc:
        raise ApiError(ErrorCode.STOCKFISH_ERROR, str(exc))
    if decision is None:
        raise ApiError(ErrorCode.INVALID_FEN, "No legal moves in this position.")
    return {
        "data": {"move": decision.move_uci, "confidence": decision.confidence},
        "meta": build_meta(game_count=_game_count(db, player_id)),
    }


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
class CreatePlayerRequest(BaseModel):
    username: str


class ConnectChessComRequest(BaseModel):
    # Defaults to the player's own username when omitted.
    chess_com_username: str | None = None
    # Optional onboarding filter, e.g. ["blitz", "rapid"]; "daily" is always excluded.
    time_classes: list[str] | None = None


class TwinMoveRequest(BaseModel):
    fen: str


class TwinBacktestRequest(BaseModel):
    game_pgn: str


# --------------------------------------------------------------------------- #
# Routes — all require an API key (provided as a router-level dependency)
# --------------------------------------------------------------------------- #
from fastapi import APIRouter  # noqa: E402

api = APIRouter(dependencies=[Depends(require_api_key)])


# ---- Player management ----------------------------------------------------- #
@api.post("/players")
def create_player(body: CreatePlayerRequest, db: Session = Depends(get_db)):
    player = repo.get_or_create_player(db, body.username)
    db.commit()
    return success_envelope(
        {"player_id": player.id, "username": player.username},
        build_meta(player.created_at),
    )


# Must precede "/players/{player_id}" so the literal path is not parsed as an id.
@api.get("/players/compare")
def compare_player_styles(a: int, b: int, db: Session = Depends(get_db)):
    _player_or_404(db, a)
    _player_or_404(db, b)
    try:
        result = compare_players(a, b, db)
    except ValueError as exc:
        raise ApiError(ErrorCode.PROFILE_NOT_READY, str(exc))
    return success_envelope(result, build_meta(model_version=pca_version()))


@api.get("/players/{player_id}")
def get_player(player_id: int, db: Session = Depends(get_db)):
    player = _player_or_404(db, player_id)
    profile = db.get(PlayerProfile, player_id)
    gc = _game_count(db, player_id)
    data = {
        "player_id": player.id,
        "username": player.username,
        "created_at": player.created_at.isoformat() if player.created_at else None,
        "game_count": gc,
        "profile_ready": profile is not None,
        "archetype": profile.archetype if profile else None,
    }
    return success_envelope(data, build_meta(
        profile.computed_at if profile else None, None, gc))


@api.delete("/players/{player_id}")
def delete_player(player_id: int, db: Session = Depends(get_db)):
    player = _player_or_404(db, player_id)
    db.delete(player)
    db.commit()
    cache.invalidate_player(player_id)
    _remove_player_index(player_id)
    return success_envelope({"deleted": player_id})


# ---- Ingestion ------------------------------------------------------------- #
def _read_pgn(raw: bytes) -> str:
    try:
        pgn = raw.decode("utf-8")
    except UnicodeDecodeError:
        pgn = raw.decode("latin-1")
    if not pgn.strip():
        raise ApiError(ErrorCode.INVALID_PGN, "Uploaded PGN is empty.")
    return pgn


def _queue_ingest(db: Session, player: Player, pgn: str) -> IngestionJob:
    job = repo.create_job(db, player.id)
    db.commit()
    try:
        dispatch(ingest_pgn, job.id, player.id, pgn, player.username)
    except Exception as exc:  # noqa: BLE001  (broker down: keep the job queued)
        logger.warning("Could not enqueue ingest job %s: %s", job.id, exc)
    return job


@api.post("/players/{player_id}/ingest")
async def player_ingest(
    player_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    player = _player_or_404(db, player_id)
    pgn = _read_pgn(await file.read())
    job = _queue_ingest(db, player, pgn)
    return success_envelope({"job_id": job.id, "status": job.status.value})


@api.get("/players/{player_id}/ingest/status")
def player_ingest_status(player_id: int, db: Session = Depends(get_db)):
    _player_or_404(db, player_id)
    job = db.scalar(
        select(IngestionJob).where(IngestionJob.player_id == player_id)
        .order_by(IngestionJob.id.desc())
    )
    if job is None:
        return success_envelope({"status": "no_job"})
    return success_envelope({
        "job_id": job.id,
        "status": job.status.value,
        "total_games": job.total_games,
        "processed_games": job.processed_games,
        "error_log": job.error_log,
    })


# ---- Chess.com sync (Section 1) -------------------------------------------- #
@api.get("/chess-com/{username}/profile")
def chesscom_profile(username: str):
    """Public Chess.com profile — powers the onboarding avatar-confirmation step."""
    try:
        profile = get_player_profile(username)
    except ChessComClientError as exc:
        raise ApiError(ErrorCode.CHESSCOM_ERROR, str(exc))
    if not profile.get("username"):
        raise ApiError(ErrorCode.NOT_FOUND, f"No Chess.com player '{username}'.")
    return success_envelope(profile)


@api.post("/players/{player_id}/connect-chess-com")
def connect_chess_com(
    player_id: int, body: ConnectChessComRequest, db: Session = Depends(get_db)
):
    """Connect a player to a Chess.com account and kick off the initial full sync."""
    player = _player_or_404(db, player_id)
    chess_com_username = (body.chess_com_username or player.username).strip()
    try:
        profile = get_player_profile(chess_com_username)
    except ChessComClientError as exc:
        raise ApiError(ErrorCode.CHESSCOM_ERROR, str(exc))
    if not profile.get("username"):
        raise ApiError(ErrorCode.NOT_FOUND, f"No Chess.com player '{chess_com_username}'.")

    repo.set_player_chesscom(db, player, chess_com_username, profile.get("avatar"))
    job = repo.create_job(db, player.id)
    db.commit()
    try:
        dispatch(
            sync_chess_com,
            job.id, player.id, incremental=False, time_classes=body.time_classes
        )
    except Exception as exc:  # noqa: BLE001  (broker down: keep the job queued)
        logger.warning("Could not enqueue sync job %s: %s", job.id, exc)

    return success_envelope({
        "job_id": job.id,
        "status": job.status.value,
        "chess_com_username": chess_com_username,
        "avatar_url": profile.get("avatar"),
        "name": profile.get("name"),
    })


@api.get("/players/{player_id}/sync-status")
def sync_status(player_id: int, db: Session = Depends(get_db)):
    player = _player_or_404(db, player_id)
    job = db.scalar(
        select(IngestionJob).where(IngestionJob.player_id == player_id)
        .order_by(IngestionJob.id.desc())
    )
    return success_envelope({
        "job_id": job.id if job else None,
        "status": job.status.value if job else "no_job",
        "total_games": job.total_games if job else 0,
        "processed_games": job.processed_games if job else 0,
        "error_log": job.error_log if job else None,
        "chess_com_username": player.chess_com_username,
        "avatar_url": player.avatar_url,
        "last_synced_at": player.last_synced_at.isoformat() if player.last_synced_at else None,
        "game_count": _game_count(db, player_id),
    })


# ---- Profile / patterns / style ------------------------------------------- #
@api.get("/players/{player_id}/profile")
def get_profile(player_id: int, db: Session = Depends(get_db)):
    _player_or_404(db, player_id)
    payload = _profile_payload(player_id, db)
    return success_envelope(payload["data"], payload["meta"])


@api.get("/players/{player_id}/patterns")
def get_patterns(player_id: int, db: Session = Depends(get_db)):
    _player_or_404(db, player_id)
    payload = _patterns_payload(player_id, db)
    return success_envelope(payload["data"], payload["meta"])


@api.get("/players/{player_id}/style-vector")
def get_style_vector(player_id: int, db: Session = Depends(get_db)):
    _player_or_404(db, player_id)
    payload = _style_payload(player_id, db)
    return success_envelope(payload["data"], payload["meta"])


# ---- Twin gameplay --------------------------------------------------------- #
@api.post("/players/{player_id}/twin/move")
@limiter.limit("30/minute")  # exempt from the 100/min default; stricter gameplay cap
def twin_move(
    player_id: int, body: TwinMoveRequest, request: Request, db: Session = Depends(get_db)
):
    _player_or_404(db, player_id)
    _validate_fen(body.fen)
    payload = _twin_move_payload(player_id, body.fen, db)
    return success_envelope(payload["data"], payload["meta"])


@api.post("/players/{player_id}/twin/backtest")
def twin_backtest(
    player_id: int, body: TwinBacktestRequest, db: Session = Depends(get_db)
):
    _player_or_404(db, player_id)
    try:
        result = backtest_twin(player_id, body.game_pgn, db)
    except FileNotFoundError as exc:
        raise ApiError(ErrorCode.STOCKFISH_ERROR, f"Stockfish unavailable: {exc}")
    return success_envelope(result, build_meta(game_count=_game_count(db, player_id)))


# ---- Similarity ------------------------------------------------------------ #
@api.get("/players/{player_id}/similar-players")
def similar_players(player_id: int, db: Session = Depends(get_db)):
    _player_or_404(db, player_id)
    payload = _similar_players_payload(player_id, db)
    return success_envelope(payload["data"], payload["meta"])


@api.get("/players/{player_id}/similar-positions")
def similar_positions(
    player_id: int, fen: str, k: int = 5, db: Session = Depends(get_db)
):
    _player_or_404(db, player_id)
    _validate_fen(fen)
    from .index_manager import find_similar_positions

    data = [sp.to_dict() for sp in find_similar_positions(fen, player_id, k=k)]
    return success_envelope(data, build_meta(game_count=_game_count(db, player_id)))


# ---- Legacy aliases (Phases 1-6, kept for compatibility) ------------------- #
@api.post("/ingest")
async def legacy_ingest(
    username: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)
):
    pgn = _read_pgn(await file.read())
    player = repo.get_or_create_player(db, username)
    db.commit()
    job = _queue_ingest(db, player, pgn)
    return success_envelope(
        {"job_id": job.id, "player_id": player.id, "status": job.status.value}
    )


@api.get("/ingest/{job_id}/status")
def legacy_job_status(job_id: int, db: Session = Depends(get_db)):
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise ApiError(ErrorCode.NOT_FOUND, "Job not found.")
    return success_envelope({
        "job_id": job.id, "player_id": job.player_id, "status": job.status.value,
        "total_games": job.total_games, "processed_games": job.processed_games,
        "error_log": job.error_log,
    })


@api.post("/twin/{player_id}/move")
@limiter.limit("30/minute")
def legacy_twin_move(
    player_id: int, body: TwinMoveRequest, request: Request, db: Session = Depends(get_db)
):
    return twin_move(player_id, body, request, db)


@api.post("/twin/{player_id}/backtest")
def legacy_twin_backtest(
    player_id: int, body: TwinBacktestRequest, db: Session = Depends(get_db)
):
    return twin_backtest(player_id, body, db)


@api.get("/players/{player_id}/similar")
def legacy_similar_positions(
    player_id: int, fen: str, k: int = 5, db: Session = Depends(get_db)
):
    return similar_positions(player_id, fen, k, db)


app.include_router(api)


# --------------------------------------------------------------------------- #
# Health & metrics (unauthenticated for monitoring)
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    status = {"stockfish": "error", "redis": "error", "db": "error"}
    try:
        from .analyzer import find_stockfish

        find_stockfish()
        status["stockfish"] = "ok"
    except Exception:
        pass
    client = cache.get_redis()
    if client is not None:
        try:
            client.ping()
            status["redis"] = "ok"
        except Exception:
            pass
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        status["db"] = "ok"
    except Exception:
        pass
    return status


@app.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    total_players = int(db.scalar(select(func.count()).select_from(Player)) or 0)
    total_games = int(db.scalar(select(func.count()).select_from(Game)) or 0)
    queue_depth = 0
    client = cache.get_redis()
    if client is not None:
        try:
            queue_depth = int(client.llen("celery") or 0)
        except Exception:
            queue_depth = 0
    return {
        "total_players": total_players,
        "total_games_analysed": total_games,
        "queue_depth": queue_depth,
        "avg_job_time_seconds": None,
    }


# --------------------------------------------------------------------------- #
def _remove_player_index(player_id: int) -> None:
    try:
        from .index_manager import _index_path, _meta_path, _moves_path

        for path in (_index_path(player_id), _moves_path(player_id), _meta_path(player_id)):
            if os.path.exists(path):
                os.remove(path)
    except Exception:  # noqa: BLE001
        logger.debug("Could not remove index files for player %s", player_id)
