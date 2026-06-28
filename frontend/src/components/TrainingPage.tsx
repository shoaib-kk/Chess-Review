import { Chess, type Square } from "chess.js";
import {
  AlertTriangle,
  ChevronLeft,
  Dumbbell,
  Flag,
  RotateCcw,
  Swords,
  Target,
  Trophy,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Chessboard } from "react-chessboard";
import {
  apiErrorMessage,
  fetchDrill,
  fetchTrainingPlan,
  requestEngineMove,
  submitDrillAttempt,
} from "../api/client";
import type { Drill, DrillVerdict, TrainingCategory, TrainingPlan } from "../types";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";

interface TrainingPageProps {
  username: string;
}

// "Default strong": the user is meant to be tested, so the engine plays hard.
const DRILL_SKILL_LEVEL = 18;

const OBJECTIVE_COPY: Record<string, { label: string; help: string }> = {
  convert: { label: "Convert the win", help: "You're winning — bring it home without throwing it away." },
  hold: { label: "Hold the balance", help: "Roughly level — keep it that way under pressure." },
  defend: { label: "Defend", help: "You're worse — don't let it get any worse (a draw is a win here)." },
};

function formatEval(cp: number): string {
  const pawns = cp / 100;
  return `${pawns >= 0 ? "+" : ""}${pawns.toFixed(1)}`;
}

export function TrainingPage({ username }: TrainingPageProps) {
  const [plan, setPlan] = useState<TrainingPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeDrill, setActiveDrill] = useState<Drill | null>(null);
  const trimmed = username.trim();

  async function loadPlan() {
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      setPlan(await fetchTrainingPlan(trimmed));
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setPlan(null);
    setActiveDrill(null);
    if (trimmed) void loadPlan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trimmed]);

  async function startDrill(drillId: number) {
    setError(null);
    try {
      setActiveDrill(await fetchDrill(drillId));
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  function finishDrill() {
    setActiveDrill(null);
    void loadPlan();
  }

  if (!trimmed) {
    return (
      <Card>
        <CardHeader title="Training plan" eyebrow="Targeted at your weaknesses">
          Enter your Chess.com username on Home to build a plan from your own games.
        </CardHeader>
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <div className="grid h-11 w-11 place-items-center rounded-full bg-app-panelSecondary text-app-muted">
            <Dumbbell className="h-5 w-5" />
          </div>
          <p className="max-w-md text-sm text-app-muted">
            Drills are real positions from your games where things slipped — you play them out
            against Stockfish and try to convert or hold.
          </p>
        </div>
      </Card>
    );
  }

  if (activeDrill) {
    return <DrillBoard drill={activeDrill} onExit={finishDrill} />;
  }

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader title="Your training plan" eyebrow="Built from your weaknesses">
          Each category is a recurring leak in your games. Pass drills to master it, then the next
          weakness surfaces.
        </CardHeader>
        {error && (
          <div className="mb-4 flex items-start gap-3 rounded-lg bg-app-blunder/10 px-4 py-3 text-sm text-app-blunder ring-1 ring-app-blunder/30">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2} />
            <span>{error}</span>
          </div>
        )}
        {loading && !plan ? (
          <p className="py-10 text-center text-sm text-app-muted">Building your plan…</p>
        ) : plan && plan.categories.length ? (
          <div className="grid gap-4 md:grid-cols-2">
            {plan.categories.map((category) => (
              <CategoryCard key={category.name} category={category} onStart={startDrill} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 py-12 text-center text-sm text-app-muted">
            <Target className="h-6 w-6 text-app-faint" />
            <p className="max-w-md">
              No drills yet. Generate puzzles from your games first (Puzzles tab) — drills are
              assembled from the same mined positions.
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}

function CategoryCard({
  category,
  onStart,
}: {
  category: TrainingCategory;
  onStart: (drillId: number) => void;
}) {
  const pct = category.drills_total
    ? Math.round((category.drills_passed / category.drills_total) * 100)
    : 0;
  return (
    <div className="flex flex-col rounded-xl border border-app-border bg-app-panelSecondary p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-app-text">{category.name}</h3>
          <p className="mt-0.5 truncate text-xs text-app-subtle">{category.weakness_source}</p>
        </div>
        {category.mastered ? (
          <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-app-good">
            <Trophy className="h-3 w-3" /> Mastered
          </span>
        ) : (
          <span className="shrink-0 text-xs text-app-muted">
            {category.drills_passed}/{category.drills_total || "—"}
          </span>
        )}
      </div>

      <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-app-bgInset ring-1 ring-inset ring-app-border">
        <div
          className="h-full rounded-full bg-gradient-to-r from-app-accent/80 to-app-accent transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="mt-1.5 flex items-center justify-between text-[11px] text-app-subtle">
        <span>{category.mastery_pct}% to mastery</span>
        {category.phase && <span>{category.phase}</span>}
      </div>

      <div className="mt-4">
        {category.next_drill_id != null ? (
          <Button variant="primary" size="sm" onClick={() => onStart(category.next_drill_id!)}>
            <Swords className="h-4 w-4" />
            {category.drills_passed > 0 ? "Next drill" : "Start drill"}
          </Button>
        ) : category.drills_total ? (
          <p className="text-xs text-app-good">All drills passed — category complete.</p>
        ) : (
          <p className="text-xs text-app-muted">No positions mined for this category yet.</p>
        )}
      </div>
    </div>
  );
}

type DrillPhase = "playing" | "grading" | "done";

function DrillBoard({ drill, onExit }: { drill: Drill; onExit: () => void }) {
  const gameRef = useRef(new Chess(drill.fen));
  const humanColor: "w" | "b" = drill.user_color === "White" ? "w" : "b";

  const [position, setPosition] = useState(drill.fen);
  const [history, setHistory] = useState<string[]>([]);
  const [userMoves, setUserMoves] = useState(0);
  const [thinking, setThinking] = useState(false);
  const [phase, setPhase] = useState<DrillPhase>("playing");
  const [verdict, setVerdict] = useState<DrillVerdict | null>(null);
  const [error, setError] = useState<string | null>(null);

  const game = gameRef.current;
  const objective = OBJECTIVE_COPY[drill.objective] ?? { label: drill.objective, help: "" };

  function sync() {
    setPosition(game.fen());
    setHistory(game.history());
  }

  async function grade(finalFen: string, moves: string[]) {
    setPhase("grading");
    try {
      const result = await submitDrillAttempt(drill.id, { final_fen: finalFen, moves });
      setVerdict(result);
      setPhase("done");
    } catch (err) {
      setError(apiErrorMessage(err));
      setPhase("playing");
    }
  }

  async function afterUserMove(nextUserMoves: number) {
    // Reached the play-out cap, or the user's move already ended the game.
    if (game.isGameOver() || nextUserMoves >= drill.max_user_moves) {
      await grade(game.fen(), game.history());
      return;
    }
    // Engine replies as the opponent.
    setThinking(true);
    setError(null);
    try {
      const res = await requestEngineMove(game.fen(), { skillLevel: DRILL_SKILL_LEVEL });
      if (res.best_move_san) {
        game.move(res.best_move_san);
        sync();
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setThinking(false);
    }
    if (game.isGameOver()) {
      await grade(game.fen(), game.history());
    }
  }

  function makeMove(from: string, to: string, promotion = "q"): boolean {
    if (thinking || phase !== "playing" || game.turn() !== humanColor || game.isGameOver()) return false;
    try {
      const result = game.move({ from, to, promotion });
      if (!result) return false;
    } catch {
      return false;
    }
    sync();
    const next = userMoves + 1;
    setUserMoves(next);
    void afterUserMove(next);
    return true;
  }

  function isPromotion(from: string, to: string): boolean {
    const piece = game.get(from as Square);
    if (!piece || piece.type !== "p") return false;
    return (piece.color === "w" && to[1] === "8") || (piece.color === "b" && to[1] === "1");
  }

  function onPieceDrop(source: string, target: string): boolean {
    if (isPromotion(source, target)) return false;
    return makeMove(source, target);
  }

  function onPromotionPieceSelect(piece?: string, from?: string, to?: string): boolean {
    if (!piece || !from || !to) return false;
    return makeMove(from, to, piece[1].toLowerCase());
  }

  function resign() {
    // Grade from the current position (counts as not converting / not holding).
    void grade(game.fen(), game.history());
  }

  function restart() {
    gameRef.current = new Chess(drill.fen);
    setPosition(drill.fen);
    setHistory([]);
    setUserMoves(0);
    setVerdict(null);
    setError(null);
    setPhase("playing");
  }

  const draggable = phase === "playing" && !thinking && game.turn() === humanColor && !game.isGameOver();
  const movesLeft = Math.max(0, drill.max_user_moves - userMoves);

  const status =
    phase === "grading"
      ? "Grading your play-out…"
      : phase === "done"
        ? verdict?.verdict === "pass"
          ? "Passed"
          : "Did not pass"
        : thinking
          ? "Engine thinking…"
          : game.turn() === humanColor
            ? `Your move (${drill.user_color})`
            : "Opponent to move";

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-accent/80">{drill.category}</p>
          <h3 className="mt-1 text-lg font-semibold tracking-tight text-app-text">{objective.label}</h3>
          <p className="mt-0.5 text-xs text-app-muted">{objective.help}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-app-subtle">Starting eval</p>
          <p className="nums text-lg font-semibold text-app-text">{formatEval(drill.start_eval_cp)}</p>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-app-muted">
        <Badge tone="blue">{drill.phase ?? "Position"}</Badge>
        <span className="font-mono">{status}</span>
        {phase === "playing" && (
          <span className="text-app-subtle">· {movesLeft} move{movesLeft !== 1 ? "s" : ""} left</span>
        )}
      </div>

      <div className="mx-auto max-w-[560px] overflow-hidden rounded-lg border border-app-border">
        <Chessboard
          id={`drill-${drill.id}`}
          position={position}
          boardOrientation={drill.user_color === "White" ? "white" : "black"}
          animationDuration={200}
          arePiecesDraggable={draggable}
          onPieceDrop={onPieceDrop}
          onPromotionPieceSelect={onPromotionPieceSelect}
          customDarkSquareStyle={{ backgroundColor: "#b58863" }}
          customLightSquareStyle={{ backgroundColor: "#f0d9b5" }}
          customBoardStyle={{ overflow: "hidden" }}
        />
      </div>

      {error && <p className="mt-3 text-sm text-app-blunder">{error}</p>}

      {history.length > 0 && (
        <p className="mt-3 break-words rounded-lg bg-app-panelSecondary px-3 py-2 font-mono text-xs text-app-muted">
          {history.map((san, i) => (i % 2 === 0 ? `${Math.floor(i / 2) + 1}. ${san}` : san)).join(" ")}
        </p>
      )}

      {phase === "done" && verdict && (
        <div
          className={`mt-4 rounded-lg px-4 py-3 ring-1 ring-inset ${
            verdict.verdict === "pass"
              ? "bg-app-good/10 text-app-good ring-app-good/30"
              : "bg-app-blunder/10 text-app-blunder ring-app-blunder/30"
          }`}
        >
          <p className="flex items-center gap-2 text-sm font-semibold">
            {verdict.verdict === "pass" ? <Trophy className="h-4 w-4" /> : <Flag className="h-4 w-4" />}
            {verdict.verdict === "pass" ? "Drill passed" : "Drill failed"}
          </p>
          <p className="mt-1 text-sm text-app-text/90">{verdict.reason}</p>
          <p className="mt-2 text-xs text-app-muted">
            Start {formatEval(verdict.start_eval)} →{" "}
            {verdict.final_eval != null ? formatEval(verdict.final_eval) : "—"}
            {verdict.swing != null && (
              <span> (swing {verdict.swing >= 0 ? "+" : ""}{(verdict.swing / 100).toFixed(1)})</span>
            )}
          </p>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {phase === "playing" && (
          <Button variant="control" size="sm" onClick={resign} disabled={thinking}>
            <Flag className="h-4 w-4" />
            End & grade
          </Button>
        )}
        {phase === "done" && (
          <Button variant="secondary" size="sm" onClick={restart}>
            <RotateCcw className="h-4 w-4" />
            Try again
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={onExit}>
          <ChevronLeft className="h-4 w-4" />
          Back to plan
        </Button>
      </div>
    </Card>
  );
}
