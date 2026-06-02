import type { GameSummary, MoveClassification } from "../types";
import { ClassificationBadge } from "./ui/Badge";
import { Card, CardHeader } from "./ui/Card";

interface AnalysisPanelProps {
  summary: GameSummary;
  currentIndex: number;
}

const accentClasses: Record<MoveClassification, string> = {
  Excellent: "border-app-good/70 bg-app-good/10",
  Inaccuracy: "border-app-warning/70 bg-app-warning/10",
  Mistake: "border-app-mistake/70 bg-app-mistake/10",
  Blunder: "border-app-blunder/70 bg-app-blunder/10",
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

export function AnalysisPanel({ summary, currentIndex }: AnalysisPanelProps) {
  const move = currentIndex >= 0 ? summary.move_analyses[currentIndex] : undefined;

  return (
    <Card className="overflow-hidden">
      <CardHeader title="Coach panel" eyebrow="Selected move">
        {summary.white_player} vs {summary.black_player} · {summary.result}
      </CardHeader>

      <div className="px-5 pb-5">
        {!move ? (
          <div className="rounded-lg bg-slate-950/70 p-5 text-sm text-app-muted ring-1 ring-app-border">
            Select a move from the graph, board controls, or move list to see the engine review.
          </div>
        ) : (
          <div className={`rounded-lg border p-4 ${accentClasses[move.classification]}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-app-muted">Move played</p>
                <div className="mt-1 font-mono text-2xl font-black text-app-text">
                  {move.move_number}
                  {move.color === "White" ? "." : "..."} {move.move_played}
                </div>
              </div>
              <ClassificationBadge classification={move.classification} />
            </div>

            <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-300">{coachCopy(move.classification)}</p>

            <div className="mt-4 grid gap-3 sm:grid-cols-4">
              <Metric label="Best move" value={move.best_move ?? "-"} />
              <Metric label="CP loss" value={move.cp_loss === null ? "-" : `${Math.round(move.cp_loss)} cp`} />
              <Metric label="Eval before" value={fmtEval(move.eval_before)} />
              <Metric label="Eval after" value={fmtEval(move.eval_after)} />
            </div>

            <div className="mt-4 rounded-md bg-slate-950/70 p-4 ring-1 ring-app-border">
              <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-app-muted">Principal variation</p>
              <p className="min-h-8 font-mono text-sm leading-6 text-slate-300">
                {move.pv.length ? move.pv.join(" ") : "No PV returned"}
              </p>
            </div>
          </div>
        )}

        {summary.user_username && (
          <div className="mt-4 grid gap-2 text-sm sm:grid-cols-4">
            <UserStat label="My inaccuracies" value={summary.user_inaccuracies} />
            <UserStat label="My mistakes" value={summary.user_mistakes} />
            <UserStat label="My blunders" value={summary.user_blunders} />
            <UserStat label="My result" value={summary.user_result ?? "-"} />
          </div>
        )}
      </div>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-950/70 p-3 ring-1 ring-app-border">
      <div className="text-[11px] font-bold uppercase tracking-[0.12em] text-app-muted">{label}</div>
      <div className="mt-2 truncate font-mono text-sm font-semibold text-app-text">{value}</div>
    </div>
  );
}

function UserStat({ label, value }: { label: string; value: number | string | null }) {
  return (
    <div className="rounded-md bg-app-panelSecondary/70 p-3">
      <div className="text-xs text-app-muted">{label}</div>
      <div className="mt-1 font-mono font-semibold text-app-text">{value ?? "-"}</div>
    </div>
  );
}
