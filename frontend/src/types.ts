export type MoveClassification =
  | "Book"
  | "Brilliant"
  | "Great"
  | "Best"
  | "Excellent"
  | "Good"
  | "Inaccuracy"
  | "Mistake"
  | "Miss"
  | "Blunder";

export interface CandidateMove {
  move: string;
  eval: number | null;
}

/**
 * An interactive exploration line on the review board: SAN moves played out from
 * a base position (either the current board, when the user drags a piece, or the
 * position before a move, when stepping the engine's best line / a candidate).
 */
export interface AnalysisLine {
  baseFen: string;
  moves: string[];
}
export type AnalysisMode = "fast" | "normal" | "deep";
export type TimeClassFilter = "rapid" | "blitz" | "bullet" | "";

export interface Puzzle {
  id: number;
  game_url: string | null;
  game_date: string | null;
  move_number: number;
  color: "White" | "Black";
  fen: string;
  played_move: string;
  best_move: string;
  best_move_uci: string | null;
  pv: string[];
  cp_loss: number;
  classification: "Blunder" | "Mistake";
  solved: boolean;
}

export interface PuzzleProgress {
  analyzed: number;
  total: number;
  running: boolean;
  puzzle_count: number;
}

export type PuzzlePhase = "opening" | "middlegame" | "endgame";
export type PuzzlePhaseFilter = "all" | PuzzlePhase;
export type PuzzleDifficultyFilter = "all" | "blunders" | "mistakes";

export interface PuzzlePhaseCounts {
  all: number;
  opening: number;
  middlegame: number;
  endgame: number;
}

export interface PuzzleFilters {
  phase?: PuzzlePhaseFilter;
  difficulty?: PuzzleDifficultyFilter;
}

export interface PuzzleList {
  puzzles: Puzzle[];
  total_puzzles: number;
  analyzed_games: number;
  phase_counts: PuzzlePhaseCounts;
  progress: PuzzleProgress;
}

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
  top_moves: CandidateMove[];
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

export interface EngineMoveResponse {
  best_move_san: string | null;
  best_move_uci: string | null;
  fen: string;
  is_game_over: boolean;
  is_check: boolean;
  eval_cp: number | null;
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
    games_with_accuracy: number;
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

// ── training layer (drills / daily / progress / inbox) ──────────────────────

export type DrillObjective = "convert" | "hold" | "defend";
export type Verdict = "pass" | "fail";

export interface TrainingCategory {
  name: string;
  weakness_source: string;
  phase: string | null;
  drills_total: number;
  drills_passed: number;
  mastery_pct: number;
  mastered: boolean;
  next_drill_id: number | null;
}

export interface TrainingPlan {
  username: string;
  max_user_moves: number;
  categories: TrainingCategory[];
}

export interface Drill {
  id: number;
  category: string;
  fen: string;
  user_color: "White" | "Black";
  start_eval_cp: number;
  objective: DrillObjective;
  phase: string | null;
  source_game_id: number;
  max_user_moves: number;
}

export interface DrillVerdict {
  drill_id: number;
  objective: DrillObjective;
  verdict: Verdict;
  start_eval: number;
  final_eval: number | null;
  swing: number | null;
  reason: string;
}

export interface Streak {
  current_streak: number;
  longest_streak: number;
  last_completed_date: string | null;
}

export interface SrsMeta {
  interval_stage: number;
  due_date: string;
  last_result: string | null;
}

export type SrsPuzzle = Puzzle & { srs?: SrsMeta };

export interface DailyData {
  date: string;
  daily_set: Puzzle[];
  due_cards: SrsPuzzle[];
  streak: Streak;
}

export interface DailyResult {
  scheduled: { interval_stage: number; due_date: string; last_result: string };
  streak: Streak;
}

export interface ProgressDelta {
  label: string;
  direction: "up" | "down" | "flat";
  improved: boolean;
  change: number;
  unit: string;
  text: string;
}

export interface ProgressWindow {
  games: number;
  avg_accuracy: number | null;
  blunders: number;
  blunder_rate: number | null;
}

export interface TrainingActivityWindow {
  attempts: number;
  passed: number;
}

export interface TrainingActivity {
  this_week: TrainingActivityWindow;
  last_week: TrainingActivityWindow;
  passed_delta: number;
  top_phase: string | null;
  top_phase_passed: number;
  headline: string | null;
  active: boolean;
}

export interface ProgressSummary {
  username: string;
  current_window: ProgressWindow;
  previous_window: ProgressWindow;
  deltas: ProgressDelta[];
  has_comparison: boolean;
  streak: Streak;
  training?: TrainingActivity;
}

export interface InboxGame {
  id: number;
  game_url: string | null;
  game_date: string | null;
  white_player: string;
  black_player: string;
  result: string | null;
  opening: string | null;
  pgn: string;
}

export interface InboxData {
  games: InboxGame[];
  count: number;
}

// ── Opponent scouting (/scout/{username}) ────────────────────────────────────

export type ScoutTimeClass = TimeClassFilter | "daily";

/** Result/expectation numbers for a group of the scouted player's games (their POV). */
export interface ScoutStats {
  games: number;
  frequency: number | null;
  wins: number;
  draws: number;
  losses: number;
  score_pct: number;
  expected_pct: number | null;
  /** Actual minus rating-expected score, in percentage points. Negative = they underperform. */
  perf_delta: number | null;
  /** perf_delta shrunk toward 0 for small samples (the ranking signal). */
  shrunk_delta: number;
  confidence: "low" | "medium" | "high";
  avg_accuracy: number | null;
  /** Mean Stockfish eval after move 12, centipawns, their POV (engine pass only). */
  avg_eval_cp: number | null;
  evaluated_games: number;
  early_loss_rate: number;
  avg_opening_time_pct: number | null;
  avg_book_depth: number | null;
  avg_first_think: number | null;
  avg_opp_rating: number | null;
  last_played: string | null;
}

export interface ScoutFamiliarity {
  score: number;
  label: "Main weapon" | "Comfortable" | "Occasional" | "Rarely seen";
  components: { volume: number; book_depth: number; speed: number };
}

export interface ScoutFamilyRow extends ScoutStats {
  family: string;
  eco: string;
  familiarity: ScoutFamiliarity;
  main_line: string;
  main_line_path: string[];
  main_line_games: number;
  variations: Array<ScoutStats & { variation: string }>;
  recent_games: Array<{
    date: string | null;
    url: string | null;
    foe: string;
    result: "win" | "draw" | "loss";
    variation: string | null;
    own_rating: number | null;
    foe_rating: number | null;
  }>;
}

export interface ScoutMoveRow extends ScoutStats {
  move: string;
  replies: Array<ScoutStats & { move: string }>;
  families?: Array<ScoutStats & { family: string }>;
}

export interface ScoutTreeNode {
  san: string | null;
  ply: number;
  path: string[];
  fen: string;
  by: "them" | "you" | null;
  avg_time_pct: number | null;
  games: number;
  wins: number;
  draws: number;
  losses: number;
  score_pct: number;
  expected_pct: number | null;
  perf_delta: number | null;
  shrunk_delta: number;
  avg_eval_cp: number | null;
  evaluated_games: number;
  avg_accuracy: number | null;
  frequency?: number;
  children: ScoutTreeNode[];
}

export interface ScoutLine {
  opponent_color: "white" | "black";
  path: string[];
  line: string;
  fen: string;
  games: number;
  share_of_parent: number;
  score_pct: number;
  expected_pct: number | null;
  perf_delta: number | null;
  shrunk_delta: number;
  avg_eval_cp: number | null;
  early_loss_rate: number;
  reason: string;
}

export interface ScoutDecisionPoint {
  opponent_color: "white" | "black";
  path: string[];
  line: string;
  fen: string;
  games: number;
  score_pct: number;
  perf_delta: number | null;
  replies: Array<{ san: string; games: number; score_pct: number }>;
  avg_time_pct: number | null;
  reason: string;
}

export interface ScoutTermination {
  reason: string;
  games: number;
  pct: number;
}

export interface ScoutMatchup {
  username: string;
  games: number;
  you_white: Array<{
    move: string;
    your_games: number;
    your_score_pct: number;
    their_games: number;
    their_score_pct: number | null;
    their_shrunk_delta: number;
    likely_lines: Array<{
      family: string;
      their_share: number;
      their_score_pct: number;
      your_games: number;
      your_score_pct: number | null;
    }>;
    edge: number;
  }>;
  you_black: Array<{
    their_move: string;
    their_share: number;
    options: Array<{
      reply: string;
      your_games: number;
      your_score_pct: number;
      their_games: number;
      their_score_pct: number | null;
      edge: number;
    }>;
  }>;
}

export interface ScoutingReport {
  username: string;
  filters: { limit: number; time_class: string | null; rated_only: boolean; engine: boolean; me: string | null };
  profile: {
    games: number;
    ratings: Record<string, number>;
    time_classes: Record<string, number>;
    overall: ScoutStats;
    white: ScoutStats;
    black: ScoutStats;
    avg_game_length: number | null;
    terminations: { win: ScoutTermination[]; loss: ScoutTermination[]; draw: ScoutTermination[] };
    long_games: ScoutStats;
    short_games: ScoutStats;
    clock_games: number;
  };
  baseline: { avg_move_time_pct: number | null; avg_opening_time_pct: number | null };
  families: { white: ScoutFamilyRow[]; black: ScoutFamilyRow[] };
  as_white: { games: number; first_moves: ScoutMoveRow[] };
  as_black: { games: number; vs_first_moves: ScoutMoveRow[] };
  tree: { white: ScoutTreeNode; black: ScoutTreeNode };
  steer_into: ScoutLine[];
  avoid: ScoutLine[];
  decision_points: ScoutDecisionPoint[];
  recent_changes: Array<{
    color: "white" | "black";
    family: string;
    recent_share: number;
    earlier_share: number;
    direction: "new" | "dropped";
    recent_games: number;
  }>;
  engine: { enabled: boolean; available?: boolean; depth?: number; eval_ply?: number; evaluated_games?: number; error?: string };
  game_plan: { you_white: string[]; you_black: string[]; general: string[] };
  matchup: ScoutMatchup | null;
  /** Added in scout v2 (contracts below). */
  habits: ScoutHabits | null;
  head_to_head: ScoutHeadToHead | null;
}

// ── Scout v2 contracts ───────────────────────────────────────────────────────
// Shared between backend/services/scout_* modules and frontend/src/components/scout/*.
// All scores/percentages are 0–100. All evals are centipawns from the SCOUTED
// PLAYER'S point of view unless a field says otherwise (mate clipped to ±10000).

/** Result split used by the habit sections. Same meaning as the ScoutStats fields. */
export interface ScoutSplit {
  key: string;
  label: string;
  games: number;
  score_pct: number;
  expected_pct: number | null;
  perf_delta: number | null;
  shrunk_delta: number;
}

/** report.habits: engine-free, computed in backend/services/scout_habits.py. */
export interface ScoutHabits {
  sessions: {
    /** Games closer together than this (minutes) count as one session. */
    session_gap_minutes: number;
    sessions: number;
    avg_games_per_session: number | null;
    after_loss: ScoutSplit;
    after_win: ScoutSplit;
    after_draw: ScoutSplit;
    /** Keys "1", "2", "3", "4-5", "6+" = game number within a session. */
    by_session_index: ScoutSplit[];
    /** Score when already on a losing streak of 2+ within the session. */
    on_losing_streak: ScoutSplit;
  };
  /** Local time (shifted by the tz_offset the client sent). Keys: night 0-6, morning 6-12, afternoon 12-18, evening 18-24. */
  time_of_day: ScoutSplit[];
  /** Keys "mon".."sun", local time. */
  weekday: ScoutSplit[];
  /** Position-type comfort. Keys include: queenless, opposite_castling, same_side_castling, open_center,
   *  closed_center, isolated_queen_pawn, bishop_pair_for, bishop_pair_against, rook_endgame,
   *  minor_piece_endgame, pawn_endgame, queen_endgame. `share` = % of their games with that feature. */
  positions: Array<ScoutSplit & { description: string; share: number }>;
  resignation: {
    resignations: number;
    /** Resigned while material was level or better for them (piece values 1/3/3/5/9). */
    resigned_not_behind: number;
    resigned_not_behind_pct: number;
    avg_material_at_resign: number | null;
    /** Losses by checkmate/time while 5+ points of material down: they play on in lost positions. */
    played_on_lost: number;
    played_on_lost_pct: number;
    /** Games they won or drew after being 3+ points down at some point. */
    comebacks: number;
    comeback_rate_pct: number;
    /** Games they lost after being 3+ points up at some point. */
    collapses_from_ahead: number;
    collapse_rate_pct: number;
  };
  draws: {
    draws: number;
    draw_rate_pct: number;
    by_reason: Array<{ reason: string; games: number; pct: number }>;
    /** Agreed draws where they had the higher rating. */
    agreed_as_favourite: number;
  };
  insights: string[];
}

/** report.head_to_head: games between the scouted player and `me`, taken from the scouted player's archive. */
export interface ScoutHeadToHead {
  me: string;
  games: number;
  /** All from YOUR point of view. */
  wins: number;
  draws: number;
  losses: number;
  score_pct: number;
  your_avg_accuracy: number | null;
  their_avg_accuracy: number | null;
  you_white: ScoutSplit;
  you_black: ScoutSplit;
  /** Openings the two of you keep reaching (first ~8 plies), most frequent first. */
  repeated_lines: Array<{ path: string[]; line: string; you_color: "white" | "black"; games: number; your_score_pct: number }>;
  recent: Array<{
    date: string | null;
    url: string | null;
    you_color: "white" | "black";
    result: "win" | "draw" | "loss"; // yours
    opening: string;
    time_class: string | null;
  }>;
  insights: string[];
}

// ── Deep (engine) analysis: POST/GET /scout/{username}/deep ──────────────────

export interface ScoutRefutation {
  opponent_color: "white" | "black";
  /** SAN path from the start to the position where THEY are to move. */
  path: string[];
  line: string;
  fen: string;
  node_games: number;
  /** Their habitual move here and how often they play it. */
  their_move: string;
  their_move_games: number;
  their_share: number;
  their_score_pct: number;
  /** Their POV: eval with best play vs after their habitual move. */
  eval_best_cp: number;
  eval_after_cp: number;
  loss_cp: number;
  severity: "inaccuracy" | "mistake" | "blunder";
  /** What they should play instead. */
  best_move: string;
  /** Your best reply after their habitual move, and the engine line (SAN, starting with punish_move). */
  punish_move: string;
  punish_line: string[];
  /** FEN after their habitual move (you to move). */
  fen_after: string;
}

export type ScoutMotif =
  | "hanging_piece"
  | "missed_capture"
  | "fork"
  | "pin"
  | "back_rank"
  | "missed_mate"
  | "allowed_mate"
  | "king_safety"
  | "other";

export interface ScoutMistakeExample {
  fen: string; // before their move
  played: string;
  best: string;
  cp_loss: number;
  move_number: number;
  color: "white" | "black";
  motif: ScoutMotif;
  family: string;
  url: string | null;
  clock_pct: number | null; // % of base clock left when they moved
}

export interface ScoutFingerprint {
  games_analyzed: number;
  moves_analyzed: number;
  depth: number;
  avg_cp_loss: number | null;
  accuracy_estimate: number | null;
  phases: Array<{
    phase: "opening" | "middlegame" | "endgame";
    moves: number;
    avg_cp_loss: number | null;
    mistakes: number;
    blunders: number;
    /** Blunders per 100 moves. */
    blunder_rate: number;
  }>;
  /** Per opening family: the move number where their play gets noticeably worse. */
  opening_cliffs: Array<{
    family: string;
    color: "white" | "black";
    games: number;
    cliff_move: number | null;
    avg_cp_loss_before: number | null;
    avg_cp_loss_after: number | null;
    by_move: Array<{ move: number; avg_cp_loss: number; samples: number }>;
  }>;
  motifs: Array<{ motif: ScoutMotif; label: string; count: number; pct: number; example: ScoutMistakeExample | null }>;
  time_pressure: {
    buckets: Array<{ key: string; label: string; moves: number; avg_cp_loss: number | null; blunder_rate: number }>;
  };
  conversion: {
    /** Games where they reached >= +200 at some point: how often they won. */
    winning_games: number;
    converted: number;
    converted_pct: number;
    /** Games where they were <= -200 at some point: how often they avoided losing. */
    losing_games: number;
    saved: number;
    saved_pct: number;
  };
  worst_mistakes: ScoutMistakeExample[];
  insights: string[];
}

export interface ScoutTrappyLine {
  opponent_color: "white" | "black";
  /** Position (SAN path) where THEY are to move. */
  path: string[];
  line: string;
  fen: string;
  rating_band: string; // e.g. "1400-1600"
  speeds: string[];
  lichess_games: number;
  /** A reply players at their rating often choose that scores badly for them. */
  trap_move: string;
  trap_share: number;
  trap_score_pct: number; // for the side that plays trap_move
  /** The reply that scores best for them at that rating. */
  best_move: string | null;
  best_score_pct: number | null;
  /** How many of THEIR games reached this position, and what they played. */
  their_games_here: number;
  their_moves_here: Array<{ san: string; games: number }>;
  reason: string;
}

export interface ScoutDeepResult {
  refutations: ScoutRefutation[];
  fingerprint: ScoutFingerprint | null;
  /** null when the Lichess explorer was unavailable; see lichess_error. */
  lichess_traps: ScoutTrappyLine[] | null;
  lichess_error: string | null;
  generated_at: string;
}

export interface ScoutDeepStatus {
  state: "idle" | "running" | "done" | "error";
  stage: "fetching" | "refutations" | "fingerprint" | "lichess" | "done" | null;
  progress: { done: number; total: number };
  started_at: string | null;
  error: string | null;
  result: ScoutDeepResult | null;
}

// ── Watchlist: /scout/watch (device-scoped) ──────────────────────────────────

export interface ScoutWatchAlert {
  kind: "new_games" | "new_opening" | "dropped_opening" | "rating_change";
  color: "white" | "black" | null;
  family: string | null;
  games: number;
  message: string;
}

export interface ScoutWatchFriend {
  username: string;
  added_at: string;
  last_seen_at: string | null; // when the user last marked this friend as seen
  last_game_at: string | null;
  new_games: number; // games since last_seen_at
  ratings: Record<string, number>;
  alerts: ScoutWatchAlert[];
  error: string | null; // e.g. Chess.com unreachable for this friend
}

export interface ScoutWatchList {
  friends: ScoutWatchFriend[];
}
