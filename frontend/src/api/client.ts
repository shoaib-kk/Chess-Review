import axios from "axios";
import type { AnalyzePayload, GameSummary } from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000",
  timeout: 120000,
});

export async function analyzeGame(payload: AnalyzePayload): Promise<GameSummary> {
  const response = await api.post<GameSummary>("/analyze", payload);
  return response.data;
}

export async function getHealth(): Promise<string> {
  const response = await api.get<{ status: string }>("/health");
  return response.data.status;
}
