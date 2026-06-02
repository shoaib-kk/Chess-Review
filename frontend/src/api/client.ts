import axios from "axios";
import type { AnalyzePayload, ChessComAnalyzePayload, ChessComGame, GameSummary, PlayerInsights } from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8001",
  timeout: 120000,
});

export async function analyzeGame(payload: AnalyzePayload): Promise<GameSummary> {
  const response = await api.post<GameSummary>("/analyze", payload);
  return response.data;
}

export async function fetchChessComGames(username: string, limit = 20): Promise<ChessComGame[]> {
  const response = await api.get<ChessComGame[]>(`/chesscom/${encodeURIComponent(username)}/games`, {
    params: { limit },
  });
  return response.data;
}

export async function analyzeChessComGame(payload: ChessComAnalyzePayload): Promise<GameSummary> {
  const response = await api.post<GameSummary>("/chesscom/analyze", payload);
  return response.data;
}

export async function fetchPlayerInsights(
  username: string,
  params: { limit?: number; time_class?: "rapid" | "blitz" | "bullet" | ""; rated_only?: boolean } = {},
): Promise<PlayerInsights> {
  const response = await api.get<PlayerInsights>(`/player-insights/${encodeURIComponent(username)}`, {
    params: {
      limit: params.limit ?? 200,
      time_class: params.time_class || undefined,
      rated_only: params.rated_only ?? false,
    },
  });
  return response.data;
}

export async function getHealth(): Promise<string> {
  const response = await api.get<{ status: string }>("/health");
  return response.data.status;
}

export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (error.message) return error.message;
  }
  return error instanceof Error ? error.message : "Request failed";
}
