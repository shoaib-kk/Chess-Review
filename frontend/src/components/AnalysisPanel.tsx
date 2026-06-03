import type { GameSummary, MoveClassification } from "../types";
import { ClassificationBadge } from "./ui/Badge";
import { Card } from "./ui/Card";

interface AnalysisPanelProps {
  summary: GameSummary;
  currentIndex: number;
  embedded?: boolean;
}

const accentClasses: Record<MoveClassification, string> = {
  Excellent: "border-app-good/60",
  Inaccuracy: "border-app-warning/70",
  Mistake: "border-app-mistake/80",
  Blunder: "border-app-blunder/80",
};

function fmtEval(value: number | null): string {
  if (value === null) return "-";
  if (Math.abs(value) >= 100000) return value > 0 ? "Mate" : "-Mate";
  return `${value > 0 ? "+" : ""}${(value / 100).toFixed(2)}`;
}

function coachCopy(classification: MoveClassification) {
  if (classification === "Excellent") return "Strong choice. The move stays close to the engine's preferred path.";
  if (classification === "Inaccuracy") return "Playable, but the position offered a cleaner route.";
  if (classification === "Mistake") return "This changed the evaluation noticeably. Compare it with the best move.";
  return "Critical swing. Start with the best move and principal variation.";
}

export function AnalysisPanel({ summary, currentIndex, embedded = false }: AnalysisPanelProps) {
  const move = currentIndex >= 0 ? summary.move_analyses[currentIndex] : undefined;

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
          <div className={`border-l-2 pl-4 ${accentClasses[move.classification]}`}>
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

            <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-300">{coachCopy(move.classification)}</p>

            <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_0.8fr]">
              <CoachFact label="Best move" value={move.best_move ?? "-"} large />
              <CoachFact label="Centipawn loss" value={move.cp_loss === null ? "-" : `${Math.round(move.cp_loss)} cp`} />
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <CoachFact label="Eval before" value={fmtEval(move.eval_before)} />
              <CoachFact label="Eval after" value={fmtEval(move.eval_after)} />
            </div>

            <div className="mt-4 border-t border-app-border pt-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-[0.14em] text-app-muted">Principal variation</p>
              <p className="min-h-8 font-mono text-sm leading-6 text-slate-300">
                {move.pv.length ? move.pv.join(" ") : "No PV returned"}
              </p>
            </div>
          </div>
        )}

        {summary.user_username && (
          <div className="mt-4 grid gap-2 border-t border-app-border pt-4 text-sm sm:grid-cols-4">
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

  return <Card className="overflow-hidden ring-1 ring-app-border/70">{content}</Card>;
}

function CoachFact({ label, value, large = false }: { label: string; value: string; large?: boolean }) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-[0.14em] text-app-muted">{label}</div>
      <div className={`mt-1 truncate font-mono font-medium text-app-text ${large ? "text-lg" : "text-sm"}`}>{value}</div>
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
