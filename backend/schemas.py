from typing import Literal, Optional

from pydantic import BaseModel, Field


# A heavily annotated real game is a few KB; this ceiling blocks oversized
# payloads up front, before the parser/engine sees them. The per-game ply cap
# in game_analyzer.MAX_ANALYSIS_PLIES is the precise compute guard.
MAX_PGN_CHARS = 200_000


class AnalyzeRequest(BaseModel):
    pgn: str = Field(..., min_length=1, max_length=MAX_PGN_CHARS)
    depth: int = Field(default=16, ge=1, le=24)
    mode: Literal["fast", "normal", "deep"] = "normal"


class MoveAnalysisResponse(BaseModel):
    move_number: int
    color: str
    move_played: str
    eval_before: Optional[float]
    eval_after: Optional[float]
    eval_white_pov: Optional[float]
    best_move: Optional[str]
    cp_loss: Optional[float]
    move_accuracy: Optional[float] = None
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
    username: str = Field(..., min_length=1, max_length=64)
    pgn: str = Field(..., min_length=1, max_length=MAX_PGN_CHARS)
    depth: int = Field(default=16, ge=1, le=24)
    mode: Literal["fast", "normal", "deep"] = "normal"


class EngineMoveRequest(BaseModel):
    fen: str = Field(..., min_length=1)
    depth: int = Field(default=12, ge=1, le=20)
    # Stockfish "Skill Level" (0 = weakest, 20 = full strength). None = uncapped.
    skill_level: Optional[int] = Field(default=None, ge=0, le=20)


class EngineMoveResponse(BaseModel):
    best_move_san: Optional[str]
    best_move_uci: Optional[str]
    fen: str  # resulting FEN after the engine's move (unchanged if the game is over)
    is_game_over: bool
    is_check: bool
    eval_cp: Optional[int] = None  # centipawns from the side-to-move POV, before the move
