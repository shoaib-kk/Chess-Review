import { Chess } from "chess.js";
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Lightbulb,
  Play,
  Puzzle as PuzzleIcon,
  Search,
  Swords,
  Target,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Chessboard } from "react-chessboard";
import { apiErrorMessage, fetchPuzzles, markPuzzleSolved, triggerPuzzleAnalysis } from "../api/client";
import type { Puzzle, PuzzleDifficultyFilter, PuzzlePhaseFilter, PuzzleProgress } from "../types";
import { ExploreBoard } from "./ExploreBoard";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";

interface PuzzlePageProps {
  username: string;
}

type PuzzleTheme = "all" | "mate" | "fork" | "pin";

const POLL_INTERVAL_MS = 4000;

const PHASE_OPTIONS: Array<{ value: PuzzlePhaseFilter; label: string; help: string }> = [
  { value: "all", label: "Any phase", help: "Use the full set." },
  { value: "opening", label: "Opening", help: "Early move mistakes." },
  { value: "middlegame", label: "Middlegame", help: "Tactics and attacks." },
  { value: "endgame", label: "Endgame", help: "Conversion moments." },
];

const THEME_OPTIONS: Array<{ value: PuzzleTheme; label: string; help: string }> = [
  { value: "all", label: "Any theme", help: "All tactical misses." },
  { value: "mate", label: "Mate", help: "Checks and mating threats." },
  { value: "fork", label: "Fork", help: "Forcing checks and attacks." },
  { value: "pin", label: "Pin", help: "Pressure on pinned pieces." },
];

const DIFFICULTY_OPTIONS: Array<{ value: PuzzleDifficultyFilter; label: string; help: string }> = [
  { value: "all", label: "Mixed", help: "Mistakes and blunders." },
  { value: "mistakes", label: "Easier", help: "Smaller misses first." },
  { value: "blunders", label: "Hard swings", help: "Big evaluation drops." },
];

function themeMatches(puzzle: Puzzle, theme: PuzzleTheme) {
  if (theme === "all") return true;
  if (theme === "mate") return puzzle.best_move.includes("#") || puzzle.pv.some((move) => move.includes("#"));
  if (theme === "fork") return puzzle.best_move.includes("+") || /^[NQBR]/.test(puzzle.best_move);
  if (theme === "pin") return /^[BQRR]/.test(puzzle.best_move) || puzzle.pv.some((move) => /^[BQRR]/.test(move));
  return true;
}

function filterByTheme(puzzles: Puzzle[], theme: PuzzleTheme) {
  const filtered = puzzles.filter((puzzle) => themeMatches(puzzle, theme));
  return filtered.length ? filtered : puzzles;
}

export function PuzzlePage({ username }: PuzzlePageProps) {
  const [phase, setPhase] = useState<PuzzlePhaseFilter>("all");
  const [theme, setTheme] = useState<PuzzleTheme>("all");
  const [difficulty, setDifficulty] = useState<PuzzleDifficultyFilter>("all");
  const [puzzles, setPuzzles] = useState<Puzzle[]>([]);
  const [progress, setProgress] = useState<PuzzleProgress>({ analyzed: 0, total: 0, running: false, puzzle_count: 0 });
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [trainingStarted, setTrainingStarted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const trimmedUsername = username.trim();

  function stopPoll() {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  }

  async function load(shouldShowLoading = false) {
    if (!trimmedUsername) return;
    if (shouldShowLoading) setLoading(true);
    try {
      const data = await fetchPuzzles(trimmedUsername, {
        phase: phase === "all" ? undefined : phase,
        difficulty: difficulty === "all" ? undefined : difficulty,
      });
      setPuzzles(filterByTheme(data.puzzles, theme));
      setProgress(data.progress);
      if (!data.progress.running) stopPoll();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      if (shouldShowLoading) setLoading(false);
    }
  }

  useEffect(() => {
    stopPoll();
    setError(null);
    setIndex(0);
    setTrainingStarted(false);
    setPuzzles([]);
    setProgress({ analyzed: 0, total: 0, running: false, puzzle_count: 0 });
  }, [trimmedUsername]);

  useEffect(() => {
    if (!trainingStarted) return;
    setIndex(0);
    load(true);
  }, [phase, difficulty, theme]);

  useEffect(() => () => stopPoll(), []);

  useEffect(() => {
    if (!progress.running) stopPoll();
  }, [progress.running]);

  async function startTraining() {
    if (!trimmedUsername) return;
    setTrainingStarted(true);
    setError(null);
    await load(true);
  }

  async function handleAnalyzeMore() {
    if (!trimmedUsername) return;
    try {
      setError(null);
      await triggerPuzzleAnalysis(trimmedUsername);
      setTrainingStarted(true);
      setProgress((p) => ({ ...p, running: true, total: Math.max(p.total, 200) }));
      stopPoll();
      pollRef.current = setInterval(() => load(false), POLL_INTERVAL_MS);
      await load(true);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  function handleSolved(id: number) {
    setPuzzles((prev) => prev.map((p) => (p.id === id ? { ...p, solved: true } : p)));
    markPuzzleSolved(trimmedUsername, id).catch(() => {});
  }

  const puzzle = puzzles[index] ?? null;

  if (!trimmedUsername) {
    return (
      <Card>
        <CardHeader title="Puzzles" eyebrow="Personal tactics">
          Enter your Chess.com username on Home to build puzzles from your public games.
        </CardHeader>
        <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
          <div className="grid h-11 w-11 place-items-center rounded-full bg-app-accentSoft text-app-accent">
            <PuzzleIcon className="h-5 w-5" />
          </div>
          <p className="max-w-md text-sm text-app-muted">
            Puzzles are made from your own missed chances, so this tool needs a public Chess.com game history.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <div className="grid gap-5">
      <Card className="overflow-hidden">
        <CardHeader title="Puzzle Training" eyebrow="From your past games">
          Pick what you want to practice, then start a focused set built from your own mistakes.
        </CardHeader>

        <div className="px-5 pb-5">
          {error && (
            <div className="mb-4 flex items-start gap-3 rounded-lg bg-app-blunder/10 px-4 py-3 text-sm text-app-blunder ring-1 ring-app-blunder/30">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2} />
              <span>{error}</span>
            </div>
          )}

          <div className="grid gap-4 lg:grid-cols-3">
            <OptionGroup title="Phase" options={PHASE_OPTIONS} value={phase} onChange={setPhase} />
            <OptionGroup title="Theme" options={THEME_OPTIONS} value={theme} onChange={setTheme} />
            <OptionGroup title="Difficulty" options={DIFFICULTY_OPTIONS} value={difficulty} onChange={setDifficulty} />
          </div>

          <div className="mt-5 flex flex-col gap-3 rounded-lg border border-app-border bg-app-panelSecondary/40 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-medium text-app-text">Train from real game mistakes</p>
              <p className="mt-1 text-xs text-app-muted">
                Building fresh puzzles analyzes up to 200 games and can take a minute.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" disabled={loading || progress.running} onClick={startTraining}>
                <Play className="h-4 w-4" />
                {loading ? "Loading..." : "Start"}
              </Button>
              <Button variant="primary" disabled={loading || progress.running} onClick={handleAnalyzeMore}>
                <Swords className="h-4 w-4" />
                {progress.running ? "Building..." : "Build puzzles"}
              </Button>
            </div>
          </div>

          {(progress.running || progress.total > 0) && (
            <div className="mt-4 rounded-lg border border-app-accent/30 bg-app-accentSoft px-4 py-3">
              <div className="mb-2 flex items-center justify-between gap-3 text-xs text-app-muted">
                <span className="font-medium text-app-text">
                  {progress.running
                    ? `Building your puzzles: game ${progress.analyzed} of ${progress.total || 200}`
                    : `${progress.analyzed} games analyzed`}
                </span>
                <span>{progress.puzzle_count} puzzle{progress.puzzle_count !== 1 ? "s" : ""} found</span>
              </div>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-app-panelSecondary">
                <div
                  className="h-full rounded-full bg-app-accent transition-all duration-500"
                  style={{ width: progress.total > 0 ? `${Math.min(100, (progress.analyzed / progress.total) * 100)}%` : "8%" }}
                />
              </div>
              {progress.running && (
                <p className="mt-2 text-xs text-app-muted">Stockfish is reviewing your public games in the background.</p>
              )}
            </div>
          )}

          {trainingStarted && !loading && !progress.running && puzzles.length === 0 && (
            <div className="mt-5 flex flex-col items-center py-8 text-center text-sm text-app-muted">
              <div className="mb-3 grid h-12 w-12 place-items-center rounded-xl bg-app-accentSoft text-app-accent">
                <Search className="h-6 w-6" strokeWidth={2} />
              </div>
              No puzzles match this set yet. Try a broader phase/theme or build fresh puzzles.
            </div>
          )}

          {trainingStarted && puzzles.length > 0 && (
            <div className="mt-5 flex items-center justify-between text-xs text-app-muted">
              <span className="inline-flex items-center gap-2">
                Puzzle {index + 1} / {puzzles.length}
                {puzzle?.solved && (
                  <span className="inline-flex items-center gap-1 text-app-good">
                    <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
                    solved
                  </span>
                )}
              </span>
              <div className="flex gap-2">
                <Button variant="control" size="sm" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
                  <ChevronLeft className="h-4 w-4" />
                  Prev
                </Button>
                <Button variant="control" size="sm" disabled={index === puzzles.length - 1} onClick={() => setIndex((i) => i + 1)}>
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>

      {trainingStarted && puzzle && (
        <PuzzleBoard
          key={puzzle.id}
          puzzle={puzzle}
          theme={theme}
          onSolved={() => handleSolved(puzzle.id)}
        />
      )}
    </div>
  );
}

function OptionGroup<T extends string>({
  title,
  options,
  value,
  onChange,
}: {
  title: string;
  options: Array<{ value: T; label: string; help: string }>;
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div>
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-app-muted">{title}</p>
      <div className="grid gap-2">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`rounded-lg border px-3 py-2 text-left transition ${
              value === option.value
                ? "border-app-accent bg-app-accentSoft text-app-text"
                : "border-app-border bg-app-panelSecondary/40 text-app-muted hover:border-app-borderStrong hover:text-app-text"
            }`}
          >
            <span className="block text-sm font-medium">{option.label}</span>
            <span className="mt-0.5 block text-xs opacity-80">{option.help}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

type PuzzleResult = "idle" | "correct" | "wrong" | "revealed";

interface PuzzleBoardProps {
  puzzle: Puzzle;
  theme: PuzzleTheme;
  onSolved: () => void;
}

function PuzzleBoard({ puzzle, theme, onSolved }: PuzzleBoardProps) {
  const [chess] = useState(() => new Chess(puzzle.fen));
  const [position, setPosition] = useState(puzzle.fen);
  const [result, setResult] = useState<PuzzleResult>("idle");
  const [attempts, setAttempts] = useState(0);
  const [hintLevel, setHintLevel] = useState(0);
  const [pvIndex, setPvIndex] = useState(0);
  const [exploreFen, setExploreFen] = useState<string | null>(null);
  const pvTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const boardOrientation = puzzle.color === "White" ? "white" : "black";
  const continuation = puzzle.pv.slice(1);

  useEffect(() => {
    if (result !== "correct" || pvIndex >= continuation.length) return;
    pvTimeout.current = setTimeout(() => {
      try {
        const moveResult = chess.move(continuation[pvIndex]);
        if (moveResult) {
          setPosition(chess.fen());
          setPvIndex((i) => i + 1);
        }
      } catch {
        // Some SAN returned by the engine can be hard to replay after promotion/castling edge cases.
      }
    }, 700);
    return () => {
      if (pvTimeout.current) clearTimeout(pvTimeout.current);
    };
  }, [result, pvIndex]);

  function onPieceDrop(source: string, target: string): boolean {
    if (result !== "idle") return false;

    let moveResult;
    try {
      moveResult = chess.move({ from: source, to: target, promotion: "q" });
    } catch {
      return false;
    }

    const played = moveResult.from + moveResult.to + (moveResult.promotion ?? "");
    const bestUci = puzzle.best_move_uci ?? "";
    const correct = played === bestUci || played.slice(0, 4) === bestUci.slice(0, 4);

    if (correct) {
      setPosition(chess.fen());
      setResult("correct");
      onSolved();
    } else {
      chess.undo();
      const next = attempts + 1;
      setAttempts(next);
      setHintLevel(Math.max(hintLevel, Math.min(2, next)));
      setResult("wrong");
      setTimeout(() => setResult("idle"), 1200);
    }
    return correct;
  }

  function reveal() {
    try {
      const moveResult = chess.move(puzzle.best_move);
      if (moveResult) setPosition(chess.fen());
    } catch {}
    setResult("revealed");
    onSolved();
  }

  const hint = buildHint(puzzle, theme, hintLevel);
  const statusText =
    result === "correct"
      ? `Correct. Best move: ${puzzle.best_move}`
      : result === "revealed"
        ? `Solution: ${puzzle.best_move}`
        : result === "wrong"
          ? "Not quite. Look for the forcing move."
          : puzzle.color === "White"
            ? "White to move. Find the best move."
            : "Black to move. Find the best move.";

  const statusColor =
    result === "correct" || result === "revealed"
      ? "text-app-good"
      : result === "wrong"
        ? "text-app-blunder"
        : "text-app-muted";

  if (exploreFen) {
    return (
      <ExploreBoard
        fen={exploreFen}
        orientation={boardOrientation}
        onExit={() => setExploreFen(null)}
        title="Play out from this puzzle"
      />
    );
  }

  return (
    <Card className="overflow-hidden">
      <div className="px-5 py-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Badge tone={puzzle.classification === "Blunder" ? "red" : "orange"}>
              {puzzle.classification}
            </Badge>
            <span className="text-xs text-app-muted">
              Move {puzzle.move_number} - {lossLabel(puzzle.cp_loss)}
            </span>
          </div>
          {puzzle.game_url && (
            <a
              href={puzzle.game_url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-app-muted underline decoration-dotted underline-offset-2 transition hover:text-app-text"
            >
              {puzzle.game_date ?? "View game"} opens Chess.com
            </a>
          )}
        </div>

        <p className={`mb-2 font-mono text-sm font-medium ${statusColor}`}>{statusText}</p>
        <p className="mb-3 flex items-center gap-2 text-sm text-app-muted">
          <Target className="h-4 w-4 text-app-accent" />
          These puzzles come from moves where your game review found a missed stronger move.
        </p>

        <div className="mx-auto max-w-[520px]">
          <Chessboard
            id={`puzzle-${puzzle.id}`}
            position={position}
            boardOrientation={boardOrientation}
            animationDuration={180}
            arePiecesDraggable={result === "idle" || result === "wrong"}
            onPieceDrop={onPieceDrop}
            customDarkSquareStyle={{ backgroundColor: "#b58863" }}
            customLightSquareStyle={{ backgroundColor: "#f0d9b5" }}
            customBoardStyle={{ overflow: "hidden" }}
          />
        </div>

        {hint && result === "idle" && (
          <div className="mt-4 rounded-lg border border-app-border bg-app-panelSecondary/50 px-4 py-3 text-sm text-app-muted">
            <span className="font-medium text-app-text">Hint:</span> {hint}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-3">
          {result === "idle" && hintLevel < 2 && (
            <Button variant="ghost" size="sm" onClick={() => setHintLevel((level) => level + 1)}>
              <Lightbulb className="h-4 w-4" />
              Hint
            </Button>
          )}
          {result === "idle" && (attempts >= 2 || hintLevel >= 2) && (
            <Button variant="ghost" size="sm" onClick={reveal}>
              <Lightbulb className="h-4 w-4" />
              Show solution
            </Button>
          )}
          <Button variant="secondary" size="sm" onClick={() => setExploreFen(position)}>
            <Swords className="h-4 w-4" />
            Play it out
          </Button>
          {(result === "correct" || result === "revealed") && continuation.length > 0 && pvIndex < continuation.length && (
            <p className="text-xs text-app-muted">Engine line: {continuation.join(" ")}</p>
          )}
          {(result === "correct" || result === "revealed") && pvIndex >= continuation.length && continuation.length > 0 && (
            <p className="text-xs text-app-muted">Full line: {puzzle.pv.join(" ")}</p>
          )}
        </div>

        {(result === "correct" || result === "revealed") && (
          <p className="mt-2 text-xs text-app-muted">
            In your game you played <span className="font-mono text-app-blunder">{puzzle.played_move}</span>.
          </p>
        )}
      </div>
    </Card>
  );
}

function buildHint(puzzle: Puzzle, theme: PuzzleTheme, level: number) {
  if (level <= 0) return "";
  if (level === 1) {
    if (theme === "mate") return "Start by checking the king or creating an immediate mate threat.";
    if (theme === "fork") return "Look for a move that attacks two important targets at once.";
    if (theme === "pin") return "Look for a line piece aiming through a defender toward a more valuable piece.";
    return `The missed chance was a ${puzzle.classification.toLowerCase()} from move ${puzzle.move_number}.`;
  }
  const piece = puzzle.best_move.match(/^[KQRBN]/)?.[0] ?? "pawn";
  return piece === "pawn" ? "The best move starts with a pawn move." : `The best move starts with the ${pieceName(piece)}.`;
}

function pieceName(piece: string) {
  return {
    K: "king",
    Q: "queen",
    R: "rook",
    B: "bishop",
    N: "knight",
  }[piece] ?? piece;
}

function lossLabel(cpLoss: number) {
  if (cpLoss >= 300) return "big swing";
  if (cpLoss >= 150) return "clear missed chance";
  return "small missed chance";
}
