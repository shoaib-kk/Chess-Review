import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import {
  analyzeChessComGame,
  analyzeGame,
  apiErrorMessage,
  fetchChessComGames,
  fetchOpeningRepertoire,
  fetchPlayerInsights,
  getHealth,
} from "./api/client";
import { AnalysisPanel } from "./components/AnalysisPanel";
import { AppShell } from "./components/AppShell";
import { ChessboardPanel } from "./components/ChessBoardPanel";
import { ChessComImport } from "./components/ChessComImport";
import { EvalGraphPanel } from "./components/EvalGraph";
import { Header } from "./components/Header";
import { HomeDashboard } from "./components/HomeDashboard";
import { MoveListPanel } from "./components/MoveList";
import { OpeningRepertoirePage } from "./components/OpeningRepertoirePage";
import { PlayerInsightsPage } from "./components/PlayerInsightsPage";
import { PuzzlePage } from "./components/PuzzlePage";
import { PgnInput } from "./components/PgnInput";
import { SummaryStrip } from "./components/SummaryStrip";
import { SAMPLE_GAME_PGN } from "./data/sampleGame";
import type { AnalysisMode, ChessComGame, GameSummary, OpeningRepertoire, PlayerInsights, TimeClassFilter } from "./types";

type AppMode = "home" | "chesscom" | "pgn" | "insights" | "repertoire" | "puzzles";
const USERNAME_STORAGE_KEY = "cr_username";

export default function App() {
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "down">("checking");
  const [activeMode, setActiveMode] = useState<AppMode>("home");
  const [sharedUsername, setSharedUsername] = useState(() => localStorage.getItem(USERNAME_STORAGE_KEY) ?? "");
  const [chessComAnalysisMode, setChessComAnalysisMode] = useState<AnalysisMode>("normal");
  const [playerInsightsLimit, setPlayerInsightsLimit] = useState(200);
  const [playerInsightsTimeClass, setPlayerInsightsTimeClass] = useState<TimeClassFilter>("");
  const [playerInsightsRatedOnly, setPlayerInsightsRatedOnly] = useState(false);
  const [playerInsights, setPlayerInsights] = useState<PlayerInsights | null>(null);
  const [playerInsightsLoading, setPlayerInsightsLoading] = useState(false);
  const [repertoireLimit, setRepertoireLimit] = useState(500);
  const [repertoireTimeClass, setRepertoireTimeClass] = useState<TimeClassFilter>("");
  const [repertoireRatedOnly, setRepertoireRatedOnly] = useState(false);
  const [openingRepertoire, setOpeningRepertoire] = useState<OpeningRepertoire | null>(null);
  const [repertoireLoading, setRepertoireLoading] = useState(false);
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

  useEffect(() => {
    const trimmed = sharedUsername.trim();
    if (trimmed) localStorage.setItem(USERNAME_STORAGE_KEY, trimmed);
    else localStorage.removeItem(USERNAME_STORAGE_KEY);
  }, [sharedUsername]);

  useEffect(() => {
    if (!summary) return;
    const currentSummary = summary;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      if (event.altKey || event.ctrlKey || event.metaKey) return;

      const target = event.target as HTMLElement | null;
      if (target?.isContentEditable) return;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;

      event.preventDefault();
      setMoveIndex((currentIndex) => {
        const navigationIndexes =
          reviewMyMovesOnly && currentSummary.user_color
            ? currentSummary.move_analyses
                .map((move, index) => (move.color === currentSummary.user_color ? index : -2))
                .filter((index) => index >= 0)
            : currentSummary.move_analyses.map((_, index) => index);

        if (!navigationIndexes.length) return -1;
        const firstIndex = reviewMyMovesOnly ? navigationIndexes[0] ?? -1 : -1;
        const lastIndex = navigationIndexes[navigationIndexes.length - 1] ?? currentSummary.total_moves - 1;

        if (event.key === "ArrowLeft") {
          if (reviewMyMovesOnly) {
            return [...navigationIndexes].reverse().find((index) => index < currentIndex) ?? firstIndex;
          }
          return Math.max(-1, currentIndex - 1);
        }

        if (reviewMyMovesOnly) {
          return navigationIndexes.find((index) => index > currentIndex) ?? lastIndex;
        }
        return Math.min(currentSummary.total_moves - 1, currentIndex + 1);
      });
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [reviewMyMovesOnly, summary]);

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
      setSharedUsername(username);
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
      setSharedUsername(username);
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
    params: { limit: number; time_class: TimeClassFilter; rated_only: boolean },
  ): Promise<PlayerInsights | null> {
    setPlayerInsightsLoading(true);
    setError(null);
    try {
      setSharedUsername(username);
      const result = await fetchPlayerInsights(username, params);
      setPlayerInsights(result);
      setApiStatus("ok");
      return result;
    } catch (err) {
      setError(apiErrorMessage(err));
      return null;
    } finally {
      setPlayerInsightsLoading(false);
    }
  }

  async function handleFetchOpeningRepertoire(
    username: string,
    params: { limit: number; time_class: TimeClassFilter; rated_only: boolean },
  ): Promise<OpeningRepertoire | null> {
    setRepertoireLoading(true);
    setError(null);
    try {
      setSharedUsername(username);
      const result = await fetchOpeningRepertoire(username, params);
      setOpeningRepertoire(result);
      setApiStatus("ok");
      return result;
    } catch (err) {
      setError(apiErrorMessage(err));
      return null;
    } finally {
      setRepertoireLoading(false);
    }
  }

  function startNewReview() {
    setSummary(null);
    setMoveIndex(-1);
    setReviewMyMovesOnly(false);
    setError(null);
  }

  function importAnotherGame() {
    startNewReview();
    setActiveMode("chesscom");
  }

  function handleLogout() {
    setSharedUsername("");
    setPlayerInsights(null);
    setOpeningRepertoire(null);
    startNewReview();
    setActiveMode("home");
  }

  async function handleTrySample() {
    setActiveMode("pgn");
    await handleAnalyze(SAMPLE_GAME_PGN, 16, "normal");
  }

  return (
    <AppShell>
      <Header
        activeMode={activeMode}
        onModeChange={setActiveMode}
        username={sharedUsername.trim()}
        onLogout={handleLogout}
        onNewReview={summary ? startNewReview : undefined}
      />

      <main className="mx-auto w-full max-w-7xl px-4 py-6 lg:ml-60 lg:px-6">
        {error && (
          <div className="mb-6 flex items-start gap-3 rounded-lg bg-app-blunder/10 px-4 py-3 text-sm text-app-blunder ring-1 ring-app-blunder/30">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2} />
            <span>{error}</span>
          </div>
        )}

        {activeMode === "home" ? (
          <HomeDashboard
            apiStatus={apiStatus}
            username={sharedUsername}
            onUsernameChange={(value) => setSharedUsername(value.trim())}
            onImportGame={() => setActiveMode("chesscom")}
            onPastePgn={() => setActiveMode("pgn")}
            onTrySample={handleTrySample}
            onOpenInsights={() => setActiveMode("insights")}
            onOpenRepertoire={() => setActiveMode("repertoire")}
            onOpenPuzzles={() => setActiveMode("puzzles")}
            sampleLoading={loading}
          />
        ) : activeMode === "puzzles" ? (
                <PuzzlePage username={sharedUsername} />
              ) : !summary ? (
              <div className="mx-auto max-w-3xl">
                {activeMode === "chesscom" ? (
                  <ChessComImport
                    loading={loading}
                    username={sharedUsername}
                    onUsernameChange={setSharedUsername}
                    mode={chessComAnalysisMode}
                    onModeChange={setChessComAnalysisMode}
                    onFetchGames={handleFetchChessComGames}
                    onAnalyzeGame={handleAnalyzeChessComGame}
                  />
                ) : activeMode === "pgn" ? (
                  <PgnInput loading={loading} onAnalyze={handleAnalyze} />
                ) : activeMode === "insights" ? (
                  <PlayerInsightsPage
                    loading={loading || playerInsightsLoading}
                    insights={playerInsights}
                    username={sharedUsername}
                    onUsernameChange={setSharedUsername}
                    limit={playerInsightsLimit}
                    onLimitChange={setPlayerInsightsLimit}
                    timeClass={playerInsightsTimeClass}
                    onTimeClassChange={setPlayerInsightsTimeClass}
                    ratedOnly={playerInsightsRatedOnly}
                    onRatedOnlyChange={setPlayerInsightsRatedOnly}
                    onFetchInsights={handleFetchPlayerInsights}
                  />
                ) : (
                  <OpeningRepertoirePage
                    loading={loading || repertoireLoading}
                    repertoire={openingRepertoire}
                    username={sharedUsername}
                    onUsernameChange={setSharedUsername}
                    limit={repertoireLimit}
                    onLimitChange={setRepertoireLimit}
                    timeClass={repertoireTimeClass}
                    onTimeClassChange={setRepertoireTimeClass}
                    ratedOnly={repertoireRatedOnly}
                    onRatedOnlyChange={setRepertoireRatedOnly}
                    onFetchRepertoire={handleFetchOpeningRepertoire}
                  />
                )}
              </div>
            ) : (
              <div className="grid gap-5">
                {activeMode === "insights" ? (
                  <PlayerInsightsPage
                    loading={loading || playerInsightsLoading}
                    insights={playerInsights}
                    username={sharedUsername || summary.user_username || ""}
                    onUsernameChange={setSharedUsername}
                    limit={playerInsightsLimit}
                    onLimitChange={setPlayerInsightsLimit}
                    timeClass={playerInsightsTimeClass}
                    onTimeClassChange={setPlayerInsightsTimeClass}
                    ratedOnly={playerInsightsRatedOnly}
                    onRatedOnlyChange={setPlayerInsightsRatedOnly}
                    onFetchInsights={handleFetchPlayerInsights}
                  />
                ) : activeMode === "repertoire" ? (
                  <OpeningRepertoirePage
                    loading={loading || repertoireLoading}
                    repertoire={openingRepertoire}
                    username={sharedUsername || summary.user_username || ""}
                    onUsernameChange={setSharedUsername}
                    limit={repertoireLimit}
                    onLimitChange={setRepertoireLimit}
                    timeClass={repertoireTimeClass}
                    onTimeClassChange={setRepertoireTimeClass}
                    ratedOnly={repertoireRatedOnly}
                    onRatedOnlyChange={setRepertoireRatedOnly}
                    onFetchRepertoire={handleFetchOpeningRepertoire}
                  />
                ) : (
                <>
                <SummaryStrip
                  summary={summary}
                  reviewMyMovesOnly={reviewMyMovesOnly}
                  onReviewMyMovesOnlyChange={setReviewMyMovesOnly}
                  onImportGame={importAnotherGame}
                />

                <div className="grid items-start gap-6 xl:grid-cols-[minmax(460px,48%)_minmax(0,52%)]">
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

                  <section className="min-w-0 overflow-hidden rounded-xl border border-app-border bg-app-panel py-2 shadow-card">
                    <EvalGraphPanel summary={summary} currentIndex={moveIndex} onSelectMove={setMoveIndex} embedded />
                    <div className="h-4" />
                    <MoveListPanel
                      summary={summary}
                      currentIndex={moveIndex}
                      onSelectMove={setMoveIndex}
                      reviewMyMovesOnly={reviewMyMovesOnly}
                      embedded
                    />
                    <div className="h-4" />
                    <AnalysisPanel summary={summary} currentIndex={moveIndex} embedded />
                  </section>
                </div>
                </>
                )}
              </div>
            )}
      </main>
    </AppShell>
  );
}
