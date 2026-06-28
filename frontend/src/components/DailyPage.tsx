import { Chess } from "chess.js";
import { AlertTriangle, Check, ChevronRight, Eye, Flame, Trophy } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Chessboard } from "react-chessboard";
import { apiErrorMessage, fetchDaily, submitDailyResult } from "../api/client";
import type { DailyData, Puzzle, SrsPuzzle, Streak, Verdict } from "../types";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";

interface DailyPageProps {
  username: string;
}

type DailyItem = (Puzzle | SrsPuzzle) & { _due?: boolean };

export function DailyPage({ username }: DailyPageProps) {
  const [data, setData] = useState<DailyData | null>(null);
  const [streak, setStreak] = useState<Streak | null>(null);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trimmed = username.trim();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setIndex(0);
    fetchDaily()
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setStreak(d.streak);
      })
      .catch((err) => !cancelled && setError(apiErrorMessage(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [trimmed]);

  // Due SRS cards come first, then today's fresh set; de-duplicated by id.
  const queue = useMemo<DailyItem[]>(() => {
    if (!data) return [];
    const items: DailyItem[] = [];
    const seen = new Set<number>();
    for (const card of data.due_cards) {
      if (!seen.has(card.id)) {
        items.push({ ...card, _due: true });
        seen.add(card.id);
      }
    }
    for (const puzzle of data.daily_set) {
      if (!seen.has(puzzle.id)) {
        items.push(puzzle);
        seen.add(puzzle.id);
      }
    }
    return items;
  }, [data]);

  async function handleResult(puzzleId: number, result: Verdict) {
    try {
      const res = await submitDailyResult(puzzleId, result, trimmed || undefined);
      setStreak(res.streak);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  const current = queue[index] ?? null;
  const done = queue.length > 0 && index >= queue.length;

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader title="Daily training" eyebrow="Keep your streak alive">
          A fresh set from your recent mistakes, plus any cards due for review. Finish them to keep
          your streak going.
        </CardHeader>
        <StreakStrip streak={streak} dueCount={data?.due_cards.length ?? 0} setCount={data?.daily_set.length ?? 0} />
        {error && (
          <div className="mt-4 flex items-start gap-3 rounded-lg bg-app-blunder/10 px-4 py-3 text-sm text-app-blunder ring-1 ring-app-blunder/30">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2} />
            <span>{error}</span>
          </div>
        )}
      </Card>

      {loading ? (
        <Card>
          <p className="py-10 text-center text-sm text-app-muted">Loading today's set…</p>
        </Card>
      ) : !queue.length ? (
        <Card>
          <div className="flex flex-col items-center gap-3 py-12 text-center text-sm text-app-muted">
            <Flame className="h-6 w-6 text-app-faint" />
            <p className="max-w-md">
              No cards yet. Generate puzzles from your games (Puzzles tab) to fill your daily set.
            </p>
          </div>
        </Card>
      ) : done ? (
        <Card>
          <div className="flex flex-col items-center gap-3 py-12 text-center">
            <div className="grid h-12 w-12 place-items-center rounded-full bg-app-good/15 text-app-good">
              <Check className="h-6 w-6" strokeWidth={2.5} />
            </div>
            <h3 className="text-lg font-semibold text-app-text">Daily set complete</h3>
            <p className="text-sm text-app-muted">
              Current streak: {streak?.current_streak ?? 0} day{(streak?.current_streak ?? 0) !== 1 ? "s" : ""}. Come back tomorrow.
            </p>
          </div>
        </Card>
      ) : current ? (
        <>
          <div className="flex items-center justify-between text-xs text-app-muted">
            <span>
              Card {index + 1} / {queue.length}
              {(current as DailyItem)._due && <span className="ml-2 text-app-accent">review due</span>}
            </span>
          </div>
          <DailyCard
            key={current.id}
            puzzle={current}
            onResolved={(result) => handleResult(current.id, result)}
            onNext={() => setIndex((i) => i + 1)}
          />
        </>
      ) : null}
    </div>
  );
}

function StreakStrip({
  streak,
  dueCount,
  setCount,
}: {
  streak: Streak | null;
  dueCount: number;
  setCount: number;
}) {
  return (
    <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Stat icon={<Flame className="h-4 w-4 text-app-accent" />} label="Current streak" value={`${streak?.current_streak ?? 0}`} />
      <Stat icon={<Trophy className="h-4 w-4 text-app-warning" />} label="Longest" value={`${streak?.longest_streak ?? 0}`} />
      <Stat label="Today's set" value={`${setCount}`} />
      <Stat label="Reviews due" value={`${dueCount}`} />
    </div>
  );
}

function Stat({ icon, label, value }: { icon?: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-app-border bg-app-bgInset px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-app-subtle">
        {icon}
        {label}
      </div>
      <div className="mt-1 nums text-xl font-semibold text-app-text">{value}</div>
    </div>
  );
}

type CardState = "idle" | "wrong" | "passed" | "failed";

function DailyCard({
  puzzle,
  onResolved,
  onNext,
}: {
  puzzle: Puzzle;
  onResolved: (result: Verdict) => void;
  onNext: () => void;
}) {
  const [chess] = useState(() => new Chess(puzzle.fen));
  const [position, setPosition] = useState(puzzle.fen);
  const [state, setState] = useState<CardState>("idle");
  const resolvedRef = useRef(false);

  const orientation = puzzle.color === "White" ? "white" : "black";
  const interactive = state === "idle" || state === "wrong";

  function resolve(result: Verdict, nextState: CardState) {
    if (resolvedRef.current) return;
    resolvedRef.current = true;
    setState(nextState);
    onResolved(result);
  }

  function onPieceDrop(source: string, target: string): boolean {
    if (!interactive) return false;
    const before = chess.fen();
    let move;
    try {
      move = chess.move({ from: source, to: target, promotion: "q" });
    } catch {
      return false;
    }
    const played = move.from + move.to + (move.promotion ?? "");
    const expected = puzzle.best_move_uci ?? "";
    const correct = played === expected || played.slice(0, 4) === expected.slice(0, 4) || chess.isCheckmate();
    if (correct) {
      setPosition(chess.fen());
      resolve("pass", "passed");
      return true;
    }
    chess.load(before);
    setState("wrong");
    setTimeout(() => setState((s) => (s === "wrong" ? "idle" : s)), 1000);
    return false;
  }

  function reveal() {
    try {
      const move = chess.move(puzzle.best_move);
      if (move) setPosition(chess.fen());
    } catch {
      /* ignore */
    }
    resolve("fail", "failed");
  }

  const statusText =
    state === "passed"
      ? `Correct — ${puzzle.best_move}`
      : state === "failed"
        ? `Solution: ${puzzle.best_move}`
        : state === "wrong"
          ? "Not the move — try again."
          : `${puzzle.color} to move. Find the best move.`;
  const statusColor =
    state === "passed" ? "text-app-good" : state === "failed" || state === "wrong" ? "text-app-blunder" : "text-app-muted";

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <Badge tone={puzzle.classification === "Blunder" ? "red" : "orange"}>{puzzle.classification}</Badge>
        <span className="text-xs text-app-muted">Move {puzzle.move_number}</span>
      </div>
      <p className={`mb-3 font-mono text-sm font-medium ${statusColor}`}>{statusText}</p>

      <div className="mx-auto max-w-[520px]">
        <Chessboard
          id={`daily-${puzzle.id}`}
          position={position}
          boardOrientation={orientation}
          animationDuration={180}
          arePiecesDraggable={interactive}
          onPieceDrop={onPieceDrop}
          customDarkSquareStyle={{ backgroundColor: "#b58863" }}
          customLightSquareStyle={{ backgroundColor: "#f0d9b5" }}
          customBoardStyle={{ overflow: "hidden" }}
        />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {interactive && (
          <Button variant="ghost" size="sm" onClick={reveal}>
            <Eye className="h-4 w-4" />
            Reveal (counts as miss)
          </Button>
        )}
        {(state === "passed" || state === "failed") && (
          <Button variant="primary" size="sm" onClick={onNext}>
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        )}
      </div>
    </Card>
  );
}
