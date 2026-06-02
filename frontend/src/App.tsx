import { useEffect, useState } from "react";
import { analyzeChessComGame, analyzeGame, apiErrorMessage, fetchChessComGames, fetchPlayerInsights, getHealth } from "./api/client";
import { AnalysisPanel } from "./components/AnalysisPanel";
import { AppShell } from "./components/AppShell";
import { ChessboardPanel } from "./components/ChessBoardPanel";
import { ChessComImport } from "./components/ChessComImport";
import { EvalGraphPanel } from "./components/EvalGraph";
import { Header } from "./components/Header";
import { MoveListPanel } from "./components/MoveList";
import { PlayerInsightsPage } from "./components/PlayerInsightsPage";
import { PgnInput } from "./components/PgnInput";
import { SummaryStrip } from "./components/SummaryStrip";
import type { AnalysisMode, ChessComGame, GameSummary, PlayerInsights } from "./types";

export default function App() {
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "down">("checking");
  const [activeMode, setActiveMode] = useState<"chesscom" | "pgn" | "insights">("chesscom");
  const [summary, setSummary] = useState<GameSummary | null>(null);
  const [moveIndex, setMoveIndex] = useState(-1);
  const [flipped, setFlipped] = useState(false);
  const [reviewMyMovesOnly, setReviewMyMovesOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealth()
      .then(() => setApiStatus("ok"))
      .catch(() => setApiStatus("down"));
  }, []);

  async function handleAnalyze(pgn: string, depth: number, mode: AnalysisMode) {
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeGame({ pgn, depth, mode });
      setSummary(result);
      setMoveIndex(-1);
      setReviewMyMovesOnly(false);
      setFlipped(false);
      setApiStatus("ok");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleFetchChessComGames(username: string): Promise<ChessComGame[]> {
    setError(null);
    try {
      const games = await fetchChessComGames(username);
      setApiStatus("ok");
      return games;
    } catch (err) {
      setError(apiErrorMessage(err));
      return [];
    }
  }

  async function handleAnalyzeChessComGame(username: string, pgn: string, mode: AnalysisMode) {
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeChessComGame({ username, pgn, depth: 16, mode });
      setSummary(result);
      setMoveIndex(-1);
      setFlipped(result.user_color === "Black");
      setReviewMyMovesOnly(false);
      setApiStatus("ok");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleFetchPlayerInsights(
    username: string,
    params: { limit: number; time_class: "rapid" | "blitz" | "bullet" | ""; rated_only: boolean },
  ): Promise<PlayerInsights | null> {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchPlayerInsights(username, params);
      setApiStatus("ok");
      return result;
    } catch (err) {
      setError(apiErrorMessage(err));
      return null;
    } finally {
      setLoading(false);
    }
  }

  function startNewReview() {
    setSummary(null);
    setMoveIndex(-1);
    setReviewMyMovesOnly(false);
    setError(null);
  }

  return (
    <AppShell>
      <Header
        apiStatus={apiStatus}
        activeMode={activeMode}
        onModeChange={setActiveMode}
        onNewReview={summary ? startNewReview : undefined}
      />

      <main className="mx-auto w-full max-w-7xl px-4 py-6 lg:px-6">
        {error && (
          <div className="mb-5 rounded-lg bg-app-blunder/10 px-4 py-3 text-sm text-red-200 ring-1 ring-app-blunder/25">
            {error}
          </div>
        )}

        {!summary ? (
          <div className="mx-auto max-w-3xl">
            {activeMode === "chesscom" ? (
              <ChessComImport
                loading={loading}
                onFetchGames={handleFetchChessComGames}
                onAnalyzeGame={handleAnalyzeChessComGame}
              />
            ) : activeMode === "pgn" ? (
              <PgnInput loading={loading} onAnalyze={handleAnalyze} />
            ) : (
              <PlayerInsightsPage loading={loading} onFetchInsights={handleFetchPlayerInsights} />
            )}
          </div>
        ) : (
          <div className="grid gap-5">
            {activeMode === "insights" ? (
              <PlayerInsightsPage
                loading={loading}
                onFetchInsights={handleFetchPlayerInsights}
                initialUsername={summary.user_username}
              />
            ) : (
            <>
            <SummaryStrip summary={summary} />

            {summary.user_username && (
              <section className="flex flex-col gap-3 rounded-lg bg-app-panel px-5 py-4 shadow-panel ring-1 ring-app-border/70 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-app-muted">Player perspective</p>
                  <p className="mt-1 text-sm text-slate-300">
                    Reviewing {summary.user_username} as {summary.user_color} vs {summary.opponent_username ?? "opponent"}
                  </p>
                </div>
                <label className="flex items-center gap-3 text-sm font-semibold text-app-text">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-app-accent"
                    checked={reviewMyMovesOnly}
                    onChange={(event) => setReviewMyMovesOnly(event.target.checked)}
                  />
                  Review my moves only
                </label>
              </section>
            )}

            <div className="grid gap-5 lg:grid-cols-[minmax(360px,45%)_minmax(0,55%)]">
              <div className="min-w-0">
                <ChessboardPanel
                  summary={summary}
                  moveIndex={moveIndex}
                  flipped={flipped}
                  reviewMyMovesOnly={reviewMyMovesOnly}
                  onFlip={() => setFlipped((value) => !value)}
                  onMoveIndexChange={setMoveIndex}
                />
              </div>

              <div className="grid min-w-0 gap-5">
                <EvalGraphPanel summary={summary} currentIndex={moveIndex} onSelectMove={setMoveIndex} />
                <MoveListPanel
                  summary={summary}
                  currentIndex={moveIndex}
                  onSelectMove={setMoveIndex}
                  reviewMyMovesOnly={reviewMyMovesOnly}
                />
                <AnalysisPanel summary={summary} currentIndex={moveIndex} />
              </div>
            </div>
            </>
            )}
          </div>
        )}
      </main>
    </AppShell>
  );
}
