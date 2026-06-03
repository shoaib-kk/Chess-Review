from typing import Literal, Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    pgn: str = Field(..., min_length=1)
    depth: int = Field(default=16, ge=1, le=24)
    mode: Literal["fast", "normal", "deep"] = "normal"
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
    opening_name: Optional[str] = None
    eco_code: Optional[str] = None
    opening_matched_plies: int = 0
    white_inaccuracies: int
    white_mistakes: int
    white_blunders: int
    black_inaccuracies: int
    black_mistakes: int
    black_blunders: int
    white_accuracy: Optional[float]
    black_accuracy: Optional[float]
    user_accuracy: Optional[float] = None
    average_cp_loss_white: Optional[float]
    average_cp_loss_black: Optional[float]
    average_cp_loss_user: Optional[float] = None
    user_color: Optional[str] = None
    user_username: Optional[str] = None
    opponent_username: Optional[str] = None
    user_result: Optional[str] = None
    user_inaccuracies: Optional[int] = None
    user_mistakes: Optional[int] = None
    user_blunders: Optional[int] = None
    move_analyses: list[MoveAnalysisResponse]


class HealthResponse(BaseModel):
    status: str


class ChessComGameResponse(BaseModel):
    white_username: str
    black_username: str
    white_result: Optional[str] = None
    black_result: Optional[str] = None
    result: str
    end_time: Optional[int] = None
    date: Optional[str] = None
    time_class: Optional[str] = None
    time_control: Optional[str] = None
    rated: bool = False
    rules: Optional[str] = None
    url: Optional[str] = None
    pgn: str


class ChessComAnalyzeRequest(BaseModel):
    username: str = Field(..., min_length=1)
    pgn: str = Field(..., min_length=1)
    depth: int = Field(default=16, ge=1, le=24)
    mode: Literal["fast", "normal", "deep"] = "normal"
    stockfish_path: Optional[str] = None
