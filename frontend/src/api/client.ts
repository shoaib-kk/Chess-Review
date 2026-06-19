import axios from "axios";
import type {
  AnalyzePayload,
  ChessComAnalyzePayload,
  ChessComGame,
  EngineMoveResponse,
  GameSummary,
  OpeningRepertoire,
  PlayerInsights,
  PuzzleList,
  PuzzleProgress,
  PuzzleDifficultyFilter,
  PuzzlePhaseFilter,
  TimeClassFilter,
} from "../types";

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
  params: { limit?: number; time_class?: TimeClassFilter; rated_only?: boolean } = {},
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

export async function fetchOpeningRepertoire(
  username: string,
  params: { limit?: number; time_class?: TimeClassFilter; rated_only?: boolean } = {},
): Promise<OpeningRepertoire> {
  const response = await api.get<OpeningRepertoire>(`/opening-repertoire/${encodeURIComponent(username)}`, {
    params: {
      limit: params.limit ?? 500,
      time_class: params.time_class || undefined,
      rated_only: params.rated_only ?? false,
    },
  });
  return response.data;
}

export async function getHealth(): Promise<string> {
  // Use the root health route rather than "/health" — ad blockers / privacy
  // extensions match the word "health" in request paths and block the ping,
  // which would otherwise show the app as "Offline" for those users.
  const response = await api.get<{ status: string }>("/");
  return response.data.status;
}

export async function fetchPuzzles(
  username: string,
  params: { limit?: number; offset?: number; phase?: PuzzlePhaseFilter; difficulty?: PuzzleDifficultyFilter } = {},
): Promise<PuzzleList> {
  const response = await api.get<PuzzleList>(`/puzzles/${encodeURIComponent(username)}`, { params });
  return response.data;
}

export async function fetchPuzzleProgress(username: string): Promise<PuzzleProgress> {
  const response = await api.get<PuzzleProgress>(`/puzzles/${encodeURIComponent(username)}/progress`);
  return response.data;
}

export async function triggerPuzzleAnalysis(username: string): Promise<void> {
  await api.post(`/puzzles/${encodeURIComponent(username)}/analyze`);
}

export async function markPuzzleSolved(username: string, puzzleId: number): Promise<void> {
  await api.post(`/puzzles/${encodeURIComponent(username)}/${puzzleId}/solved`);
}

export async function requestEngineMove(
  fen: string,
  opts: { depth?: number; skillLevel?: number } = {},
): Promise<EngineMoveResponse> {
  const response = await api.post<EngineMoveResponse>("/play/move", {
    fen,
    depth: opts.depth ?? 12,
    skill_level: opts.skillLevel,
  });
  return response.data;
}

export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 429) {
      return "The app is doing a lot at once. Please wait a moment before trying again.";
    }
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      if (/too many requests|rate limit/i.test(detail)) {
        return "Too many requests for the moment. Give it a few seconds, then try again.";
      }
      if (/network|timeout|failed/i.test(detail)) return "That request did not finish. Please try again.";
      return detail;
    }
    if (error.code === "ECONNABORTED") return "That took too long to finish. Please try again.";
    if (error.message) return "The request could not be completed. Please try again.";
  }
  return error instanceof Error ? error.message : "Request failed";
}
