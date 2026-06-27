// Response shapes for the Player Modelling Engine API (Section 7 deliverable).
// Every engine response is wrapped in the uniform {success, data, error, meta}
// envelope; `data` shapes mirror the backend Pydantic/JSON payloads.

export interface ApiMeta {
  computed_at: string | null;
  model_version: number | null;
  game_count: number | null;
}

export interface ApiEnvelope<T> {
  success: boolean;
  data: T | null;
  error: { code: string; message: string } | null;
  meta: ApiMeta;
}

// ---- Section 1: Chess.com sync -------------------------------------------- //
export interface ChessComProfile {
  username: string | null;
  avatar: string | null;
  name: string | null;
  url: string | null;
  followers: number | null;
  country: string | null;
}

export interface ConnectResponse {
  job_id: number;
  status: string;
  chess_com_username: string;
  avatar_url: string | null;
  name: string | null;
}

export type SyncJobStatus =
  | "no_job"
  | "pending"
  | "running"
  | "completed"
  | "failed";

export interface SyncStatus {
  job_id: number | null;
  status: SyncJobStatus;
  total_games: number;
  processed_games: number;
  error_log: string | null;
  chess_com_username: string | null;
  avatar_url: string | null;
  last_synced_at: string | null;
  game_count: number;
}

// ---- Section 2: Player profile -------------------------------------------- //
export interface AccuracyFeatures {
  mean_cpl: number | null;
  median_cpl: number | null;
  cpl_std: number | null;
  accuracy_score: number | null;
  blunder_rate: number | null;
  mistake_rate: number | null;
  inaccuracy_rate: number | null;
  accuracy_variance_across_games: number | null;
}

export interface TacticalFeatures {
  brilliant_move_rate: number | null;
  tactical_opportunity_conversion: number | null;
  sacrifice_tendency: number | null;
  complexity_preference: number | null;
}

export interface PositionalFeatures {
  pawn_structure_score: {
    doubled_pawns: number;
    isolated_pawns: number;
    passed_pawns: number;
  } | null;
  king_safety_index: number | null;
  piece_activity_index: number | null;
}

export interface EndgameFeatures {
  endgame_game_count: number | null;
  endgame_accuracy: number | null;
  endgame_conversion_rate: number | null;
}

export interface StyleFeatures {
  aggression_index: number | null;
  trade_preference_by_piece: Record<string, number> | null;
  queen_trade_avoidance: number | null;
  initiative_index: number | null;
}

export interface OpeningFeatures {
  eco_distribution: Record<string, number>;
  opening_repertoire_size: number | null;
  opening_accuracy: number | null;
  opening_flexibility: number | null;
}

export interface TimeFeatures {
  time_pressure_cpl: number | null;
  time_pressure_blunder_rate: number | null;
}

export interface ProfileFeatures {
  accuracy: AccuracyFeatures;
  tactical: TacticalFeatures;
  positional: PositionalFeatures;
  endgame: EndgameFeatures;
  style: StyleFeatures;
  opening: OpeningFeatures;
  time: TimeFeatures;
}

export interface ProfileResponse {
  features: ProfileFeatures;
  archetype: string | null;
}

// ---- Section 3: Behavioural patterns -------------------------------------- //
export interface BehaviouralPattern {
  pattern_type: string;
  label: string;
  description: string;
  severity_score: number;
  frequency_score: number;
  confidence: number;
  sample_count: number;
  supporting_game_ids: number[];
}

// ---- Section 6: Style embedding ------------------------------------------- //
export interface SimilarPlayer {
  player_id: number;
  username: string;
  archetype: string | null;
  distance: number;
}

export interface StyleVectorResponse {
  vector: number[];
  archetype: string | null;
  similar_players: SimilarPlayer[];
}

export interface PlayerComparison {
  distance: number;
  cosine_similarity?: number;
  shared_archetype?: boolean;
  [key: string]: unknown;
}

// ---- Section 4: Digital twin ---------------------------------------------- //
export interface TwinMoveResponse {
  move: string; // UCI
  confidence: number;
}

export interface BacktestResult {
  move_match_rate: number;
  top3_match_rate: number;
  cpl_correlation: number;
  style_match_score: number;
}

// ---- Player summary ------------------------------------------------------- //
export interface PlayerSummary {
  player_id: number;
  username: string;
  created_at: string | null;
  game_count: number;
  profile_ready: boolean;
  archetype: string | null;
}
