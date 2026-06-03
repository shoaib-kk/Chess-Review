export type MoveClassification = "Excellent" | "Inaccuracy" | "Mistake" | "Blunder";
export type AnalysisMode = "fast" | "normal" | "deep";
export type TimeClassFilter = "rapid" | "blitz" | "bullet" | "";

export interface MoveAnalysis {
  move_number: number;
  color: "White" | "Black";
  move_played: string;
  eval_before: number | null;
  eval_after: number | null;
  eval_white_pov: number | null;
  best_move: string | null;
  cp_loss: number | null;
  move_accuracy: number | null;
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
  opening_name: string | null;
  eco_code: string | null;
  opening_matched_plies: number;
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
  opening_family: string;
  variation: string | null;
  eco: string;
  games: number;
  frequency: number;
  win_rate: number;
  avg_accuracy: number | null;
  avg_cp_loss: number | null;
  variations: OpeningVariationStat[];
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
    by_phase: Array<{ category: string; count: number; percentage: number }>;
    by_type: Array<{ category: string; count: number; percentage: number }>;
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

export interface OpeningGameExample {
  date: string | null;
  opponent: string;
  color: "White" | "Black";
  result: "win" | "loss" | "draw";
  accuracy: number;
  cp_loss: number;
  game_length: number;
  url: string | null;
}

export interface OpeningResponseStat {
  move: string;
  games: number;
  frequency: number;
}

export interface OpeningVariationStat {
  variation: string;
  games: number;
  frequency: number;
  eco: string;
}

export interface OpeningResultStat {
  result: "win" | "loss" | "draw";
  games: number;
  frequency: number;
}

export type RepertoireCategory = "white" | "black_vs_e4" | "black_vs_d4" | "black_vs_other";

export interface OpeningRepertoireRow {
  id: string;
  opening_name: string;
  opening_family: string;
  variation: string | null;
  eco: string;
  category: RepertoireCategory;
  games: number;
  frequency: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
  avg_accuracy: number | null;
  avg_cp_loss: number | null;
  avg_game_length: number | null;
  variations: OpeningVariationStat[];
  recent_games: OpeningGameExample[];
  common_opponent_responses: OpeningResponseStat[];
  typical_results: OpeningResultStat[];
  best_example_games: OpeningGameExample[];
  worst_example_games: OpeningGameExample[];
}

export interface OpeningTrendPoint {
  date: string | null;
  opening_name: string;
  opening_family: string;
  variation: string | null;
  eco: string;
  category: RepertoireCategory;
  accuracy: number;
  win_rate: number;
  result: "win" | "loss" | "draw";
  game_index: number;
}

export interface OpeningTrendWindow {
  games: number;
  openings: OpeningRepertoireRow[];
}

export interface OpeningRepertoire {
  username: string;
  filters: {
    limit: number;
    time_class: "rapid" | "blitz" | "bullet" | null;
    rated_only: boolean;
  };
  summary: {
    total_games: number;
    openings_tracked: number;
    strongest_opening: OpeningRepertoireRow | null;
    weakest_opening: OpeningRepertoireRow | null;
  };
  repertoire: {
    white: OpeningRepertoireRow[];
    black: OpeningRepertoireRow[];
    black_vs_e4: OpeningRepertoireRow[];
    black_vs_d4: OpeningRepertoireRow[];
    black_vs_other: OpeningRepertoireRow[];
  };
  recommendations: {
    enough_data: boolean;
    strongest_openings: OpeningRepertoireRow[];
    weakest_openings: OpeningRepertoireRow[];
    continue_playing: OpeningRepertoireRow[];
    needs_improvement: OpeningRepertoireRow[];
    consider_reviewing: OpeningRepertoireRow[];
  };
  trends: {
    windows: {
      last_30: OpeningTrendWindow;
      last_90: OpeningTrendWindow;
      last_180: OpeningTrendWindow;
      all: OpeningTrendWindow;
    };
    points: OpeningTrendPoint[];
  };
  category_labels: Record<RepertoireCategory, string>;
}

export interface InsightWindow {
  games: number;
  win_rate: number;
  avg_accuracy: number | null;
  avg_cp_loss: number | null;
  blunders: number;
}
