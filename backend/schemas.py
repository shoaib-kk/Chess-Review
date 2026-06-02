from typing import Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    pgn: str = Field(..., min_length=1)
    depth: int = Field(default=16, ge=1, le=24)
    stockfish_path: Optional[str] = None


class MoveAnalysisResponse(BaseModel):
    move_number: int
    color: str
    move_played: str
    eval_before: Optional[float]
    eval_after: Optional[float]
    eval_white_pov: Optional[float]
    best_move: Optional[str]
    cp_loss: Optional[float]
    classification: str
    pv: list[str]
    fen_before: str
    fen_after: str
    played_move_uci: Optional[str]
    best_move_uci: Optional[str]


class GameSummaryResponse(BaseModel):
    white_player: str
    black_player: str
    event: str
    date: str
    result: str
    total_moves: int
    initial_fen: str
    white_inaccuracies: int
    white_mistakes: int
    white_blunders: int
    black_inaccuracies: int
    black_mistakes: int
    black_blunders: int
    move_analyses: list[MoveAnalysisResponse]


class HealthResponse(BaseModel):
    status: str
