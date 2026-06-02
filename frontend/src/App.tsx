import { useEffect, useState } from "react";
import { analyzeGame, getHealth } from "./api/client";
import { AnalysisPanel } from "./components/AnalysisPanel";
import { ChessBoardPanel } from "./components/ChessBoardPanel";
import { EvalGraph } from "./components/EvalGraph";
import { Header } from "./components/Header";
import { MoveList } from "./components/MoveList";
import { PgnInput } from "./components/PgnInput";
import type { GameSummary } from "./types";

export default function App() {
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "down">("checking");
  const [summary, setSummary] = useState<GameSummary | null>(null);
  const [moveIndex, setMoveIndex] = useState(-1);
  const [flipped, setFlipped] = useState(false);
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
      setApiStatus("ok");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
      setApiStatus("down");
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
        <PgnInput loading={loading} onAnalyze={handleAnalyze} />
      ) : (
        <main className="grid gap-4 px-4 py-5 lg:grid-cols-[minmax(340px,520px)_1fr] lg:px-8">
          <ChessBoardPanel
            summary={summary}
            moveIndex={moveIndex}
            flipped={flipped}
            onFlip={() => setFlipped((value) => !value)}
            onMoveIndexChange={setMoveIndex}
          />

          <div className="grid gap-4">
            <EvalGraph summary={summary} currentIndex={moveIndex} onSelectMove={setMoveIndex} />
            <MoveList summary={summary} currentIndex={moveIndex} onSelectMove={setMoveIndex} />
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
