import { useEffect, useState } from "react";
import { analyzeChessComGame, analyzeGame, apiErrorMessage, fetchChessComGames, getHealth } from "./api/client";
import { AccuracyCards } from "./components/AccuracyCards";
import { AnalysisPanel } from "./components/AnalysisPanel";
import { ChessBoardPanel } from "./components/ChessBoardPanel";
import { ChessComImport } from "./components/ChessComImport";
import { EvalGraph } from "./components/EvalGraph";
import { Header } from "./components/Header";
import { MoveList } from "./components/MoveList";
import { PgnInput } from "./components/PgnInput";
import type { ChessComGame, GameSummary } from "./types";

export default function App() {
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "down">("checking");
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

  async function handleAnalyze(pgn: string, depth: number) {
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeGame({ pgn, depth });
      setSummary(result);
      setMoveIndex(-1);
      setReviewMyMovesOnly(false);
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

  async function handleAnalyzeChessComGame(username: string, pgn: string) {
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeChessComGame({ username, pgn, depth: 16 });
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

  return (
    <div className="min-h-screen bg-app-bg">
      <Header apiStatus={apiStatus} />

      {error && (
        <div className="mx-auto mt-4 max-w-5xl rounded border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      {!summary ? (
        <main className="mx-auto grid w-full max-w-6xl gap-5 px-4 py-8 lg:grid-cols-[0.9fr_1.1fr] lg:px-8">
          <ChessComImport
            loading={loading}
            onFetchGames={handleFetchChessComGames}
            onAnalyzeGame={handleAnalyzeChessComGame}
          />
          <PgnInput loading={loading} onAnalyze={handleAnalyze} />
        </main>
      ) : (
        <main className="grid gap-4 px-4 py-5 lg:grid-cols-[minmax(340px,520px)_1fr] lg:px-8">
          <div className="lg:col-span-2">
            <AccuracyCards summary={summary} />
          </div>

          {summary.user_username && (
            <div className="lg:col-span-2 flex flex-col gap-3 rounded bg-app-panel p-4 shadow-panel sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Player Perspective</p>
                <p className="text-sm text-slate-300">
                  Reviewing {summary.user_username} as {summary.user_color} vs {summary.opponent_username ?? "opponent"}
                </p>
              </div>
              <label className="flex items-center gap-3 text-sm font-semibold text-slate-200">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-app-accent"
                  checked={reviewMyMovesOnly}
                  onChange={(event) => setReviewMyMovesOnly(event.target.checked)}
                />
                Review my moves only
              </label>
            </div>
          )}

          <ChessBoardPanel
            summary={summary}
            moveIndex={moveIndex}
            flipped={flipped}
            reviewMyMovesOnly={reviewMyMovesOnly}
            onFlip={() => setFlipped((value) => !value)}
            onMoveIndexChange={setMoveIndex}
          />

          <div className="grid gap-4">
            <EvalGraph summary={summary} currentIndex={moveIndex} onSelectMove={setMoveIndex} />
            <MoveList
              summary={summary}
              currentIndex={moveIndex}
              onSelectMove={setMoveIndex}
              reviewMyMovesOnly={reviewMyMovesOnly}
            />
          </div>

          <div className="lg:col-span-2">
            <AnalysisPanel summary={summary} currentIndex={moveIndex} />
          </div>

          <div className="lg:col-span-2 flex justify-between gap-3">
            <button className="rounded border border-white/10 px-4 py-2 text-sm text-slate-200 hover:border-app-accent" onClick={() => setSummary(null)}>
              Analyse another PGN
            </button>
          </div>
        </main>
      )}
    </div>
  );
}
