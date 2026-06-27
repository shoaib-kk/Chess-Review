// Axios client for the Player Modelling Engine (a separate service from the main
// review backend). Base URL and API key are build-time env vars; every call
// unwraps the {success, data, error, meta} envelope and throws on error.
import axios, { AxiosError } from "axios";
import type {
  ApiEnvelope,
  ApiMeta,
  BacktestResult,
  BehaviouralPattern,
  ChessComProfile,
  ConnectResponse,
  PlayerComparison,
  PlayerSummary,
  ProfileResponse,
  SimilarPlayer,
  StyleVectorResponse,
  SyncStatus,
  TwinMoveResponse,
} from "./types";

const engine = axios.create({
  baseURL: import.meta.env.VITE_PM_API_BASE_URL ?? "http://127.0.0.1:8000",
  timeout: 30000,
  headers: {
    "X-API-Key": import.meta.env.VITE_PM_API_KEY ?? "dev-master-key",
  },
});

export interface Enveloped<T> {
  data: T;
  meta: ApiMeta;
}

function unwrap<T>(body: ApiEnvelope<T>): Enveloped<T> {
  if (!body.success || body.data === null) {
    throw new EngineError(
      body.error?.code ?? "UNKNOWN",
      body.error?.message ?? "Request failed.",
    );
  }
  return { data: body.data, meta: body.meta };
}

export class EngineError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
    this.name = "EngineError";
  }
}

export function engineErrorMessage(err: unknown): string {
  if (err instanceof EngineError) return err.message;
  const ax = err as AxiosError<ApiEnvelope<unknown>>;
  if (ax?.response?.data?.error?.message) return ax.response.data.error.message;
  if (ax?.message) return ax.message;
  return "Something went wrong talking to the engine.";
}

export function engineErrorCode(err: unknown): string | null {
  if (err instanceof EngineError) return err.code;
  const ax = err as AxiosError<ApiEnvelope<unknown>>;
  return ax?.response?.data?.error?.code ?? null;
}

async function get<T>(url: string, params?: Record<string, unknown>): Promise<Enveloped<T>> {
  const res = await engine.get<ApiEnvelope<T>>(url, { params });
  return unwrap(res.data);
}

async function post<T>(url: string, body?: unknown): Promise<Enveloped<T>> {
  const res = await engine.post<ApiEnvelope<T>>(url, body);
  return unwrap(res.data);
}

// ---- Player + Chess.com sync ---------------------------------------------- //
export const createPlayer = (username: string) =>
  post<{ player_id: number; username: string }>("/players", { username });

export const getPlayer = (playerId: number) =>
  get<PlayerSummary>(`/players/${playerId}`);

export const getChessComProfile = (username: string) =>
  get<ChessComProfile>(`/chess-com/${encodeURIComponent(username)}/profile`);

export const connectChessCom = (
  playerId: number,
  body: { chess_com_username?: string; time_classes?: string[] },
) => post<ConnectResponse>(`/players/${playerId}/connect-chess-com`, body);

export const getSyncStatus = (playerId: number) =>
  get<SyncStatus>(`/players/${playerId}/sync-status`);

// ---- Profile / patterns / style ------------------------------------------- //
export const getProfile = (playerId: number) =>
  get<ProfileResponse>(`/players/${playerId}/profile`);

export const getPatterns = (playerId: number) =>
  get<BehaviouralPattern[]>(`/players/${playerId}/patterns`);

export const getStyleVector = (playerId: number) =>
  get<StyleVectorResponse>(`/players/${playerId}/style-vector`);

export const getSimilarPlayers = (playerId: number) =>
  get<SimilarPlayer[]>(`/players/${playerId}/similar-players`);

export const comparePlayers = (a: number, b: number) =>
  get<PlayerComparison>(`/players/compare`, { a, b });

// ---- Twin gameplay -------------------------------------------------------- //
export const twinMove = (playerId: number, fen: string) =>
  post<TwinMoveResponse>(`/players/${playerId}/twin/move`, { fen });

export const twinBacktest = (playerId: number, gamePgn: string) =>
  post<BacktestResult>(`/players/${playerId}/twin/backtest`, { game_pgn: gamePgn });
