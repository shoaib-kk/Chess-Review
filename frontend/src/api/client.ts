import axios from "axios";
import type {
  AnalyzePayload,
  ChessComAnalyzePayload,
  ChessComGame,
  DailyData,
  DailyResult,
  Drill,
  DrillVerdict,
  EngineMoveResponse,
  GameSummary,
  InboxData,
  OpeningRepertoire,
  PlayerInsights,
  ProgressSummary,
  PuzzleList,
  PuzzleProgress,
  PuzzleDifficultyFilter,
  PuzzlePhaseFilter,
  TimeClassFilter,
  TrainingPlan,
  Verdict,
} from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8001",
  timeout: 120000,
});

// Anonymous per-device identity: a random UUID generated on first visit and kept
// in localStorage. It scopes all of this device's data (puzzles, streaks) and is
// sent as X-Device-Id on every request. No username/password — possession of the
// (unguessable) UUID is the whole credential, and per-device data "just works".
const DEVICE_ID_STORAGE_KEY = "cr_device_id";

function generateDeviceId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // Fallback for older/insecure contexts: RFC-4122 v4 from getRandomValues.
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function getDeviceId(): string {
  let id = localStorage.getItem(DEVICE_ID_STORAGE_KEY);
  if (!id) {
    id = generateDeviceId();
    localStorage.setItem(DEVICE_ID_STORAGE_KEY, id);
  }
  return id;
}

api.interceptors.request.use((config) => {
  config.headers["X-Device-Id"] = getDeviceId();
  return config;
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
  // Owned by this device (X-Device-Id, sent automatically); payload.username is
  // the Chess.com player used for color/accuracy detection.
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

// Puzzle data is scoped to the device id (sent as X-Device-Id automatically), so
// reads need no username. Mining a fresh set still needs the Chess.com username
// whose public games should be analysed — passed in the request body.
export async function fetchPuzzles(
  params: { limit?: number; offset?: number; phase?: PuzzlePhaseFilter; difficulty?: PuzzleDifficultyFilter } = {},
): Promise<PuzzleList> {
  const response = await api.get<PuzzleList>(`/puzzles/`, { params });
  return response.data;
}

export async function fetchPuzzleProgress(): Promise<PuzzleProgress> {
  const response = await api.get<PuzzleProgress>(`/puzzles/progress`);
  return response.data;
}

export async function triggerPuzzleAnalysis(username: string): Promise<void> {
  await api.post(`/puzzles/analyze`, { username });
}

export async function markPuzzleSolved(puzzleId: number): Promise<void> {
  await api.post(`/puzzles/${puzzleId}/solved`);
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

// ── training layer ──────────────────────────────────────────────────────────
// All training data is scoped to the device id (sent as X-Device-Id), so reads
// need no username; building the plan/progress still needs the Chess.com username
// whose weaknesses drive it.

export async function fetchTrainingPlan(username: string): Promise<TrainingPlan> {
  const response = await api.get<TrainingPlan>("/training-plan", { params: { username } });
  return response.data;
}

export async function fetchDrill(drillId: number): Promise<Drill> {
  const response = await api.get<Drill>(`/drills/${drillId}`);
  return response.data;
}

export async function submitDrillAttempt(
  drillId: number,
  payload: { final_fen: string; moves?: string[]; depth?: number },
): Promise<DrillVerdict> {
  const response = await api.post<DrillVerdict>(`/drills/${drillId}/attempt`, payload);
  return response.data;
}

export async function fetchDaily(): Promise<DailyData> {
  const response = await api.get<DailyData>("/daily/");
  return response.data;
}

export async function submitDailyResult(
  puzzleId: number,
  result: Verdict,
  username?: string,
): Promise<DailyResult> {
  const response = await api.post<DailyResult>(`/daily/${puzzleId}/result`, {
    result,
    username: username || undefined,
  });
  return response.data;
}

export async function fetchProgress(username: string): Promise<ProgressSummary> {
  const response = await api.get<ProgressSummary>("/progress", { params: { username } });
  return response.data;
}

export async function fetchInbox(): Promise<InboxData> {
  const response = await api.get<InboxData>("/inbox");
  return response.data;
}

export async function refreshInbox(username: string): Promise<void> {
  await api.post("/inbox/refresh", { username });
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
