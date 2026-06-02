import type { GameSummary, MoveClassification } from "../types";

interface AnalysisPanelProps {
  summary: GameSummary;
  currentIndex: number;
}

const COLORS: Record<MoveClassification, string> = {
  Excellent: "#4ade80",
  Inaccuracy: "#facc15",
  Mistake: "#f97316",
  Blunder: "#ef4444",
};

function fmtEval(value: number | null): string {
  if (value === null) return "-";
  if (Math.abs(value) >= 100000) return value > 0 ? "Mate" : "-Mate";
  return `${value > 0 ? "+" : ""}${(value / 100).toFixed(2)}`;
}

export function AnalysisPanel({ summary, currentIndex }: AnalysisPanelProps) {
  const move = currentIndex >= 0 ? summary.move_analyses[currentIndex] : undefined;

  return (
    <section className="rounded bg-app-panel p-4 shadow-panel">
      <div className="mb-4 flex flex-col gap-3 border-b border-white/10 pb-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs text-slate-500">{summary.event} · {summary.date}</p>
          <h2 className="text-lg font-bold text-slate-50">
            <span className="text-app-lightSquare">{summary.white_player}</span>
            <span className="mx-2 text-slate-500">vs</span>
            <span className="text-app-darkSquare">{summary.black_player}</span>
          </h2>
        </div>
        <div className="rounded bg-slate-950 px-3 py-2 font-mono text-sm text-slate-200">{summary.result}</div>
      </div>

      {!move ? (
        <div className="text-sm text-slate-400">Select a move to see the engine review.</div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_1.25fr]">
          <div className="rounded border-l-4 bg-slate-950 p-4" style={{ borderColor: COLORS[move.classification] }}>
            <div className="mb-3 flex items-center justify-between">
              <div className="font-mono text-xl font-bold text-slate-50">
                {move.move_number}
                {move.color === "White" ? "." : "..."} {move.move_played}
              </div>
              <span className="rounded px-2.5 py-1 text-xs font-black text-slate-950" style={{ background: COLORS[move.classification] }}>
                {move.classification}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Stat label="Best move" value={move.best_move ?? "-"} />
              <Stat label="CP loss" value={move.cp_loss === null ? "-" : `${Math.round(move.cp_loss)} cp`} />
              <Stat label="Eval before" value={fmtEval(move.eval_before)} />
              <Stat label="Eval after" value={fmtEval(move.eval_after)} />
            </div>
          </div>

          <div className="rounded bg-slate-950 p-4">
            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Principal Variation</p>
            <p className="min-h-12 font-mono text-sm leading-6 text-slate-300">
              {move.pv.length ? move.pv.join(" ") : "No PV returned"}
            </p>
          </div>
        </div>
      )}

      <div className="mt-4 grid gap-2 text-sm sm:grid-cols-3">
        <SummaryStat label="Inaccuracies" white={summary.white_inaccuracies} black={summary.black_inaccuracies} />
        <SummaryStat label="Mistakes" white={summary.white_mistakes} black={summary.black_mistakes} />
        <SummaryStat label="Blunders" white={summary.white_blunders} black={summary.black_blunders} />
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-app-panel/70 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 font-mono font-semibold text-slate-100">{value}</div>
    </div>
  );
}

function SummaryStat({ label, white, black }: { label: string; white: number; black: number }) {
  return (
    <div className="flex items-center justify-between rounded bg-slate-950 px-3 py-2">
      <span className="text-app-lightSquare">{white}</span>
      <span className="text-slate-400">{label}</span>
      <span className="text-app-darkSquare">{black}</span>
    </div>
  );
}
