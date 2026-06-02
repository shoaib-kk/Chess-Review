from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import AnalyzeRequest, GameSummaryResponse, HealthResponse
from .serializers import serialize_game_summary

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from services.game_analyzer import analyze_pgn
except ModuleNotFoundError:
    from game_analyzer import analyze_pgn


app = FastAPI(title="Chess Game Reviewer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/analyze", response_model=GameSummaryResponse)
def analyze(request: AnalyzeRequest) -> dict:
    try:
        summary = analyze_pgn(
            pgn_text=request.pgn,
            engine_path=request.stockfish_path,
            depth=request.depth,
        )
        return serialize_game_summary(summary)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
