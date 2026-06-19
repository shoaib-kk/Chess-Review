import { Chess, type Square } from "chess.js";
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Lightbulb,
  Puzzle as PuzzleIcon,
  Search,
  Swords,
  Target,
} from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Chessboard } from "react-chessboard";
import {
  apiErrorMessage,
  fetchPuzzles,
  markPuzzleSolved,
  requestEngineMove,
  triggerPuzzleAnalysis,
} from "../api/client";
import type { Puzzle, PuzzlePhaseFilter, PuzzleProgress } from "../types";
import { ExploreBoard } from "./ExploreBoard";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";

interface PuzzlePageProps {
  username: string;
}

const POLL_INTERVAL_MS = 4000;

// Win-chance sigmoid (matches the backend) for comparing alternative solutions.
const WIN_CHANCE_K = 0.00368208;
function winChance(cp: number): number {
  const bounded = Math.max(-4000, Math.min(4000, cp));
  return 50 + 50 * (2 / (1 + Math.exp(-WIN_CHANCE_K * bounded)) - 1);
}

function randomSeed() {
  return Math.floor(Math.random() * 0x7fffffff);
}

function shuffledPuzzles(puzzles: Puzzle[], seed: number) {
  const randomRank = (id: number) => {
    let value = (id ^ seed) | 0;
    value = Math.imul(value ^ (value >>> 16), 0x45d9f3b);
    value = Math.imul(value ^ (value >>> 16), 0x45d9f3b);
    return (value ^ (value >>> 16)) >>> 0;
  };
  return [...puzzles].sort((a, b) => randomRank(a.id) - randomRank(b.id));
}

const PHASE_OPTIONS: Array<{ value: PuzzlePhaseFilter; label: string; help: string }> = [
  { value: "all", label: "Any phase", help: "Use the full set." },
  { value: "opening", label: "Opening", help: "Early move mistakes." },
  { value: "middlegame", label: "Middlegame", help: "Tactics and attacks." },
  { value: "endgame", label: "Endgame", help: "Conversion moments." },
];

export function PuzzlePage({ username }: PuzzlePageProps) {
  const [phase, setPhase] = useState<PuzzlePhaseFilter>("all");
  const [puzzles, setPuzzles] = useState<Puzzle[]>([]);
  const [progress, setProgress] = useState<PuzzleProgress>({ analyzed: 0, total: 0, running: false, puzzle_count: 0 });
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [trainingStarted, setTrainingStarted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const shuffleSeedRef = useRef(randomSeed());
  const trimmedUsername = username.trim();

  function stopPoll() {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  }

  async function load(shouldShowLoading = false, selectedPhase = phase) {
    if (!trimmedUsername) return;
    if (shouldShowLoading) setLoading(true);
    try {
      const data = await fetchPuzzles(trimmedUsername, {
        phase: selectedPhase === "all" ? undefined : selectedPhase,
      });
      setPuzzles(shuffledPuzzles(data.puzzles, shuffleSeedRef.current));
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
    shuffleSeedRef.current = randomSeed();
    setTrainingStarted(false);
    setPuzzles([]);
    setProgress({ analyzed: 0, total: 0, running: false, puzzle_count: 0 });
  }, [trimmedUsername]);

  useEffect(() => () => stopPoll(), []);

  useEffect(() => {
    if (!progress.running) stopPoll();
  }, [progress.running]);

  async function handlePhaseChange(selectedPhase: PuzzlePhaseFilter) {
    if (!trimmedUsername) return;
    shuffleSeedRef.current = randomSeed();
    setPhase(selectedPhase);
    setIndex(0);
    setPuzzles([]);
    setTrainingStarted(true);
    try {
      setError(null);
      await triggerPuzzleAnalysis(trimmedUsername);
      setProgress((p) => ({ ...p, running: true, total: Math.max(p.total, 200) }));
      stopPoll();
      pollRef.current = setInterval(() => load(false, selectedPhase), POLL_INTERVAL_MS);
      await load(true, selectedPhase);
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
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <div className="grid h-11 w-11 place-items-center rounded-full bg-app-panelSecondary text-app-muted">
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
      <Card>
        <CardHeader title="Puzzle Training" eyebrow="From your past games">
          Select a phase to immediately build a focused set from your own mistakes.
        </CardHeader>

        <div>
          {error && (
            <div className="mb-4 flex items-start gap-3 rounded-lg bg-app-blunder/10 px-4 py-3 text-sm text-app-blunder ring-1 ring-app-blunder/30">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2} />
              <span>{error}</span>
            </div>
          )}

          <OptionGroup
            title="Phase of the game"
            options={PHASE_OPTIONS}
            value={phase}
            onChange={handlePhaseChange}
            disabled={loading || progress.running}
          />

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
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-app-bgInset ring-1 ring-inset ring-app-border">
                <div
                  className="relative h-full rounded-full bg-gradient-to-r from-app-accent/80 to-app-accent transition-all duration-500"
                  style={{ width: progress.total > 0 ? `${Math.min(100, (progress.analyzed / progress.total) * 100)}%` : "8%" }}
                >
                  {progress.running && (
                    <span className="absolute inset-0 overflow-hidden rounded-full">
                      <span className="absolute inset-y-0 -left-full w-full animate-shimmer bg-gradient-to-r from-transparent via-white/25 to-transparent" />
                    </span>
                  )}
                </div>
              </div>
              {progress.running && (
                <p className="mt-2 text-xs text-app-muted">Stockfish is reviewing your public games in the background.</p>
              )}
            </div>
          )}

          {trainingStarted && !loading && !progress.running && puzzles.length === 0 && (
            <div className="mt-5 flex flex-col items-center py-8 text-center text-sm text-app-muted">
              <div className="mb-3 grid h-12 w-12 place-items-center rounded-xl bg-app-panelSecondary text-app-muted">
                <Search className="h-6 w-6" strokeWidth={2} />
              </div>
              No puzzles for this phase yet. Select a different phase to try another set.
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
              </div>
            </div>
          )}
        </div>
      </Card>

      {trainingStarted && puzzle && (
        <PuzzleBoard
          key={puzzle.id}
          puzzle={puzzle}
          onSolved={() => handleSolved(puzzle.id)}
          onNext={() => setIndex((i) => i + 1)}
          isLastPuzzle={index === puzzles.length - 1}
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
  disabled = false,
}: {
  title: string;
  options: Array<{ value: T; label: string; help: string }>;
  value: T;
  onChange: (value: T) => void;
  disabled?: boolean;
}) {
  return (
    <div>
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">{title}</p>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={`rounded-lg border px-3 py-2 text-left transition disabled:cursor-wait disabled:opacity-60 ${
              value === option.value
                ? "border-app-accent bg-app-accentSoft text-app-text"
                : "border-app-border bg-app-panelSecondary text-app-muted hover:border-app-borderStrong hover:text-app-text"
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
  onSolved: () => void;
  onNext: () => void;
  isLastPuzzle: boolean;
}

function PuzzleBoard({ puzzle, onSolved, onNext, isLastPuzzle }: PuzzleBoardProps) {
  const [chess] = useState(() => new Chess(puzzle.fen));
  const [position, setPosition] = useState(puzzle.fen);
  const [result, setResult] = useState<PuzzleResult>("idle");
  const [attempts, setAttempts] = useState(0);
  const [hintLevel, setHintLevel] = useState(0);
  const [pvIndex, setPvIndex] = useState(0);
  const [exploreFen, setExploreFen] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  // Click-to-move: the currently selected origin square and the highlight
  // styles for it plus its legal destinations.
  const [selectedSquare, setSelectedSquare] = useState<Square | null>(null);
  const [optionSquares, setOptionSquares] = useState<Record<string, CSSProperties>>({});
  const pvTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Player-POV centipawn eval after the engine's best move; computed lazily and
  // cached so alternative moves can be accepted if they're nearly as strong.
  const bestEvalRef = useRef<number | null | undefined>(undefined);

  const boardOrientation = puzzle.color === "White" ? "white" : "black";
  const interactive = !checking && (result === "idle" || result === "wrong") && pvIndex % 2 === 0;

  function clearSelection() {
    setSelectedSquare(null);
    setOptionSquares({});
  }

  /**
   * Highlight the legal destinations for the piece on `square`. Returns false
   * (and selects nothing) when the piece has no legal moves.
   */
  function showMoveOptions(square: Square): boolean {
    const moves = chess.moves({ square, verbose: true });
    if (moves.length === 0) return false;

    const styles: Record<string, CSSProperties> = {
      [square]: { background: "rgba(200,161,90,0.32)" },
    };
    for (const move of moves) {
      const occupied = chess.get(move.to);
      styles[move.to] = occupied
        ? // Capture: a ring around the target piece.
          { background: "radial-gradient(circle, transparent 54%, rgba(200,161,90,0.55) 56%)" }
        : // Quiet move: a centered dot.
          { background: "radial-gradient(circle, rgba(200,161,90,0.6) 24%, transparent 26%)" };
    }
    setSelectedSquare(square);
    setOptionSquares(styles);
    return true;
  }

  function onSquareClick(square: Square) {
    if (!interactive) return;

    // A piece is already selected: try to move it to the clicked square.
    if (selectedSquare && square !== selectedSquare) {
      const moved = onPieceDrop(selectedSquare, square);
      if (moved) {
        clearSelection();
        return;
      }
      // Not a legal destination — fall through to (re)select below.
    }

    // Select the clicked square if it holds a piece for the side to move.
    const piece = chess.get(square);
    if (piece && piece.color === chess.turn()) {
      showMoveOptions(square);
    } else {
      clearSelection();
    }
  }

  function registerWrong() {
    const next = attempts + 1;
    setAttempts(next);
    setHintLevel((level) => Math.max(level, Math.min(2, next)));
    setResult("wrong");
    setTimeout(() => setResult("idle"), 1200);
  }

  async function bestMoveEval(): Promise<number | null> {
    if (bestEvalRef.current !== undefined) return bestEvalRef.current;
    try {
      const board = new Chess(puzzle.fen);
      board.move(puzzle.best_move);
      if (board.isCheckmate()) {
        bestEvalRef.current = 100000;
      } else {
        const res = await requestEngineMove(board.fen());
        bestEvalRef.current = res.eval_cp === null ? null : -res.eval_cp;
      }
    } catch {
      bestEvalRef.current = null;
    }
    return bestEvalRef.current;
  }

  /** Accept a non-exact move if it keeps the position nearly as good as best. */
  async function isGoodAlternative(fenAfterMove: string): Promise<{ ok: boolean; replyFen: string | null }> {
    try {
      const best = await bestMoveEval();
      const res = await requestEngineMove(fenAfterMove);
      if (res.eval_cp === null) return { ok: false, replyFen: null };
      const playerEval = -res.eval_cp; // flip from opponent POV back to the solver
      const ok = best === null
        ? playerEval >= 100
        : winChance(playerEval) >= winChance(best) - 8;
      return { ok, replyFen: ok ? res.fen : null };
    } catch {
      return { ok: false, replyFen: null };
    }
  }

  useEffect(() => {
    const computerReply = pvIndex % 2 === 1 ? puzzle.pv[pvIndex] : null;
    if (result !== "idle" || !checking || !computerReply) return;
    pvTimeout.current = setTimeout(() => {
      try {
        const moveResult = chess.move(computerReply);
        if (moveResult) {
          setPosition(chess.fen());
          const nextIndex = pvIndex + 1;
          setPvIndex(nextIndex);
          if (nextIndex >= puzzle.pv.length || chess.isGameOver()) {
            setChecking(false);
            setResult("correct");
            onSolved();
          } else {
            setChecking(false);
          }
        }
      } catch {
        // Some SAN returned by the engine can be hard to replay after promotion/castling edge cases.
        setChecking(false);
        setResult("correct");
        onSolved();
      }
    }, 700);
    return () => {
      if (pvTimeout.current) clearTimeout(pvTimeout.current);
    };
  }, [checking, chess, onSolved, puzzle.pv, pvIndex, result]);

  function onPieceDrop(source: string, target: string): boolean {
    if (result !== "idle" || checking) return false;
    clearSelection();
    const fenBeforeMove = chess.fen();

    let moveResult;
    try {
      moveResult = chess.move({ from: source, to: target, promotion: "q" });
    } catch {
      return false;
    }

    const played = moveResult.from + moveResult.to + (moveResult.promotion ?? "");
    let expectedUci = pvIndex === 0 ? puzzle.best_move_uci ?? "" : "";
    try {
      const expectedBoard = new Chess(fenBeforeMove);
      const expectedMove = expectedBoard.move(puzzle.pv[pvIndex]);
      expectedUci = expectedMove.from + expectedMove.to + (expectedMove.promotion ?? "");
    } catch {}
    const exact = played === expectedUci || played.slice(0, 4) === expectedUci.slice(0, 4);

    // Exact engine move, or any move that delivers checkmate, is always accepted.
    if (exact || chess.isCheckmate()) {
      setPosition(chess.fen());
      const nextIndex = pvIndex + 1;
      setPvIndex(nextIndex);
      if (nextIndex >= puzzle.pv.length || chess.isGameOver()) {
        setResult("correct");
        onSolved();
      } else {
        setResult("idle");
        setChecking(true);
      }
      return true;
    }

    // A move that ends the game without mate (stalemate/draw) is not the idea.
    if (chess.isGameOver()) {
      chess.undo();
      registerWrong();
      return false;
    }

    // Later moves must follow the line so player and computer turns stay synchronized.
    if (pvIndex > 0) {
      chess.undo();
      setPosition(chess.fen());
      registerWrong();
      return false;
    }

    // Otherwise ask the engine whether this first-move alternative is nearly as strong.
    setPosition(chess.fen());
    setChecking(true);
    void isGoodAlternative(chess.fen()).then(({ ok, replyFen }) => {
      setChecking(false);
      if (ok) {
        if (replyFen) {
          chess.load(replyFen);
          setPosition(replyFen);
        }
        setResult("correct");
        onSolved();
      } else {
        chess.undo();
        setPosition(chess.fen());
        registerWrong();
      }
    });
    return true;
  }

  function reveal() {
    try {
      const moveResult = chess.move(puzzle.pv[pvIndex] ?? puzzle.best_move);
      if (moveResult) setPosition(chess.fen());
    } catch {}
    setResult("revealed");
    onSolved();
  }

  const hint = buildHint(puzzle, hintLevel);
  const idlePrompt = pvIndex > 0
    ? "Your turn. Find the next move."
    : puzzle.color === "White"
      ? "White to move. Find the best move."
      : "Black to move. Find the best move.";
  const statusText = checking
    ? "Checking your move…"
    : result === "correct"
      ? `Correct. Best move: ${puzzle.best_move}`
      : result === "revealed"
        ? `Solution: ${puzzle.best_move}`
        : result === "wrong"
          ? "Not quite. Look for the forcing move."
          : idlePrompt;

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
    <Card>
      <div>
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
            arePiecesDraggable={interactive}
            onPieceDrop={onPieceDrop}
            onSquareClick={onSquareClick}
            customSquareStyles={optionSquares}
            customDarkSquareStyle={{ backgroundColor: "#b58863" }}
            customLightSquareStyle={{ backgroundColor: "#f0d9b5" }}
            customBoardStyle={{ overflow: "hidden" }}
          />
        </div>

        {hint && result === "idle" && (
          <div className="mt-4 border-l-2 border-app-accent pl-3 text-sm text-app-muted">
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
          <Button variant="control" size="sm" disabled={isLastPuzzle} onClick={onNext}>
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
          {checking && pvIndex % 2 === 1 && (
            <p className="text-xs text-app-muted">Computer thinking…</p>
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

function buildHint(puzzle: Puzzle, level: number) {
  if (level <= 0) return "";
  if (level === 1) {
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
