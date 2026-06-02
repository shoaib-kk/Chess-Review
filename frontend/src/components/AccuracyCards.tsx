import type { GameSummary } from "../types";

interface AccuracyCardsProps {
  summary: GameSummary;
}

function fmt(value: number | null, suffix = "") {
  return value === null ? "-" : `${value.toFixed(1)}${suffix}`;
}

export function AccuracyCards({ summary }: AccuracyCardsProps) {
  return (
    <section className="grid gap-3 md:grid-cols-3">
      <AccuracyCard
        label="White Accuracy"
        value={fmt(summary.white_accuracy)}
        sublabel="Average CP Loss"
        subvalue={fmt(summary.average_cp_loss_white, " cp")}
        tone="text-app-lightSquare"
      />
      <AccuracyCard
        label="Black Accuracy"
        value={fmt(summary.black_accuracy)}
        sublabel="Average CP Loss"
        subvalue={fmt(summary.average_cp_loss_black, " cp")}
        tone="text-app-darkSquare"
      />
      <AccuracyCard
        label={summary.user_username ? "My Accuracy" : "Game Accuracy"}
        value={fmt(summary.user_username ? summary.user_accuracy : average(summary.white_accuracy, summary.black_accuracy))}
        sublabel={summary.user_username ? "My Avg CP Loss" : "Combined Avg CP Loss"}
        subvalue={fmt(summary.user_username ? summary.average_cp_loss_user : average(summary.average_cp_loss_white, summary.average_cp_loss_black), " cp")}
        tone="text-app-accent"
      />
    </section>
  );
}

function average(a: number | null, b: number | null): number | null {
  const values = [a, b].filter((value): value is number => value !== null);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function AccuracyCard({
  label,
  value,
  sublabel,
  subvalue,
  tone,
}: {
  label: string;
  value: string;
  sublabel: string;
  subvalue: string;
  tone: string;
}) {
  return (
    <div className="rounded bg-app-panel p-4 shadow-panel">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</p>
      <div className={`mt-2 font-mono text-3xl font-black ${tone}`}>{value}</div>
      <div className="mt-3 flex items-center justify-between rounded bg-slate-950 px-3 py-2 text-sm">
        <span className="text-slate-500">{sublabel}</span>
        <span className="font-mono font-semibold text-slate-100">{subvalue}</span>
      </div>
    </div>
  );
}
