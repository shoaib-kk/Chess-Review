export type MoveClassification = "Excellent" | "Inaccuracy" | "Mistake" | "Blunder";
export type AnalysisMode = "fast" | "normal" | "deep";

export interface MoveAnalysis {
  move_number: number;
  color: "White" | "Black";
  move_played: string;
  eval_before: number | null;
  eval_after: number | null;
  eval_white_pov: number | null;
  best_move: string | null;
  cp_loss: number | null;
  classification: MoveClassification;
  pv: string[];
  fen_before: string;
  fen_after: string;
  played_move_uci: string | null;
  best_move_uci: string | null;
}

export interface GameSummary {
  white_player: string;
  black_player: string;
  event: string;
  date: string;
  result: string;
  total_moves: number;
  initial_fen: string;
  white_inaccuracies: number;
  white_mistakes: number;
  white_blunders: number;
  black_inaccuracies: number;
  black_mistakes: number;
  black_blunders: number;
  white_accuracy: number | null;
  black_accuracy: number | null;
  user_accuracy: number | null;
  average_cp_loss_white: number | null;
  average_cp_loss_black: number | null;
  average_cp_loss_user: number | null;
  user_color: "White" | "Black" | null;
  user_username: string | null;
  opponent_username: string | null;
  user_result: string | null;
  user_inaccuracies: number | null;
  user_mistakes: number | null;
  user_blunders: number | null;
  move_analyses: MoveAnalysis[];
}

export interface AnalyzePayload {
  pgn: string;
  depth: number;
  mode: AnalysisMode;
  stockfish_path?: string;
}

export interface ChessComGame {
  white_username: string;
  black_username: string;
  white_result: string | null;
  black_result: string | null;
  result: string;
  end_time: number | null;
  date: string | null;
  time_class: string | null;
  time_control: string | null;
  rated: boolean;
  rules: string | null;
  url: string | null;
  pgn: string;
}

export interface ChessComAnalyzePayload extends AnalyzePayload {
  username: string;
}

export interface OpeningInsight {
  opening_name: string;
  eco: string;
  games: number;
  frequency: number;
  win_rate: number;
  avg_accuracy: number | null;
  avg_cp_loss: number | null;
}

export interface PlayerInsights {
  username: string;
  filters: {
    limit: number;
    time_class: "rapid" | "blitz" | "bullet" | null;
    rated_only: boolean;
  };
  summary: {
    games_analyzed: number;
    win_rate: number;
    white_win_rate: number;
    black_win_rate: number;
    average_accuracy: number | null;
    average_cp_loss: number | null;
    average_game_length: number | null;
  };
  openings: {
    as_white: OpeningInsight[];
    as_black: OpeningInsight[];
    responses_to_e4: Array<{ move: string; games: number; frequency: number }>;
    responses_to_d4: Array<{ move: string; games: number; frequency: number }>;
  };
  performance: {
    last_30: InsightWindow;
    last_90: InsightWindow;
    last_180: InsightWindow;
    trend_notes: string[];
    trend_points: Array<{
      date: string | null;
      accuracy: number;
      cp_loss: number;
      blunders: number;
      rating: number | null;
    }>;
    rating_points: Array<{ date: string; rating: number }>;
  };
  mistakes: {
    categories: Array<{ category: string; count: number; percentage: number }>;
    top_weaknesses: Array<{ category: string; count: number; percentage: number }>;
  };
  profile: {
    style: string;
    position_preference: string;
    average_game_length: number;
    preferred_openings: string[];
    summary: string;
    top_weakness: string | null;
    strengths: string[];
    weaknesses: string[];
    recommendations: string[];
  };
}

export interface InsightWindow {
  games: number;
  win_rate: number;
  avg_accuracy: number | null;
  avg_cp_loss: number | null;
  blunders: number;
}
