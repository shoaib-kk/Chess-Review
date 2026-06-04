import { useEffect, useState } from "react";
import type { GameSummary, MoveAnalysis, MoveClassification } from "../types";
import { ClassificationBadge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";

interface AnalysisPanelProps {
  summary: GameSummary;
  currentIndex: number;
  embedded?: boolean;
}

const accentClasses: Record<MoveClassification, string> = {
  Excellent: "bg-app-good/10",
  Inaccuracy: "bg-app-warning/10",
  Mistake: "bg-app-mistake/10",
  Blunder: "bg-app-blunder/10",
};

function coachCopy(classification: MoveClassification) {
  if (classification === "Excellent") return "Strong choice. The move stays close to the engine's preferred path.";
  if (classification === "Inaccuracy") return "Playable, but the position offered a cleaner route.";
  if (classification === "Mistake") return "This changed the evaluation noticeably. Compare it with the best move.";
  return "Critical swing. Start with the best move and principal variation.";
}

export function AnalysisPanel({ summary, currentIndex, embedded = false }: AnalysisPanelProps) {
  const [showBestLine, setShowBestLine] = useState(false);
  const move = currentIndex >= 0 ? summary.move_analyses[currentIndex] : undefined;

  useEffect(() => {
    setShowBestLine(false);
  }, [currentIndex]);

  const content = (
    <>
      <div className="px-5 pb-2 pt-4">
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-app-muted">Selected move</p>
        <h2 className="mt-1 text-base font-medium text-app-text">Coach panel</h2>
      </div>

      <div className="px-5 pb-5">
        {!move ? (
          <p className="py-5 text-sm text-app-muted">
            Select a move from the graph, board controls, or move list to see the engine review.
          </p>
        ) : (
          <div className={`px-4 py-4 ${accentClasses[move.classification]}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.14em] text-app-muted">Move played</p>
                <div className="mt-1 font-mono text-2xl font-medium text-app-text">
                  {move.move_number}
                  {move.color === "White" ? "." : "..."} {move.move_played}
                </div>
              </div>
              <ClassificationBadge classification={move.classification} />
            </div>

            <p className="mt-4 max-w-2xl text-sm leading-6 text-app-text">{coachCopy(move.classification)}</p>

            <div className="mt-5">
              <Button variant="secondary" size="sm" onClick={() => setShowBestLine((value) => !value)}>
                {showBestLine ? "Hide best line" : "Show best line"}
              </Button>
            </div>

            {showBestLine && <BestLine move={move} />}
          </div>
        )}

        {summary.user_username && (
          <div className="mt-6 grid gap-4 pt-1 text-sm sm:grid-cols-4">
            <UserStat label="My inaccuracies" value={summary.user_inaccuracies} />
            <UserStat label="My mistakes" value={summary.user_mistakes} />
            <UserStat label="My blunders" value={summary.user_blunders} />
            <UserStat label="My result" value={summary.user_result ?? "-"} />
          </div>
        )}
      </div>
    </>
  );

  if (embedded) return <section>{content}</section>;

  return <Card className="overflow-hidden">{content}</Card>;
}

function BestLine({ move }: { move: MoveAnalysis }) {
  const line = move.pv.length ? move.pv : move.best_move ? [move.best_move] : [];
  const bestMove = move.best_move ?? line[0] ?? "-";
  const followUp = line[0] === bestMove ? line.slice(1) : line;

  return (
    <div className="mt-5 bg-app-panel/60 px-4 py-4">
      <div className="grid gap-4 sm:grid-cols-[160px_1fr]">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-app-muted">Best move</p>
          <p className="mt-1 font-mono text-lg font-medium text-app-text">{bestMove}</p>
        </div>
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-app-muted">Follow-up line</p>
          <p className="mt-1 min-h-7 font-mono text-sm leading-6 text-app-text">
            {followUp.length ? followUp.join(" ") : "No follow-up returned"}
          </p>
        </div>
      </div>
    </div>
  );
}

function UserStat({ label, value }: { label: string; value: number | string | null }) {
  return (
    <div>
      <div className="text-xs text-app-muted">{label}</div>
      <div className="mt-1 font-mono font-medium text-app-text">{value ?? "-"}</div>
    </div>
  );
}
