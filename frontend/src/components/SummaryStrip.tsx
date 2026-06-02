import type { GameSummary } from "../types";
import { Card } from "./ui/Card";

interface SummaryStripProps {
  summary: GameSummary;
}

function fmt(value: number | null, suffix = "") {
  return value === null ? "-" : `${value.toFixed(1)}${suffix}`;
}

export function SummaryStrip({ summary }: SummaryStripProps) {
  const inaccuracies = summary.white_inaccuracies + summary.black_inaccuracies;
  const mistakes = summary.white_mistakes + summary.black_mistakes;
  const blunders = summary.white_blunders + summary.black_blunders;

  return (
    <Card className="overflow-hidden">
      <div className="grid grid-cols-2 divide-x divide-y divide-app-border/70 md:grid-cols-6 md:divide-y-0">
        <StripItem label="White Accuracy" value={fmt(summary.white_accuracy)} accent="text-app-lightSquare" />
        <StripItem label="Black Accuracy" value={fmt(summary.black_accuracy)} accent="text-app-darkSquare" />
        <StripItem label={summary.user_username ? "My Accuracy" : "Game Accuracy"} value={fmt(summary.user_username ? summary.user_accuracy : average(summary.white_accuracy, summary.black_accuracy))} accent="text-app-accent" />
        <StripItem label="Inaccuracies" value={String(summary.user_username ? summary.user_inaccuracies ?? inaccuracies : inaccuracies)} accent="text-app-warning" />
        <StripItem label="Mistakes" value={String(summary.user_username ? summary.user_mistakes ?? mistakes : mistakes)} accent="text-app-mistake" />
        <StripItem label="Blunders" value={String(summary.user_username ? summary.user_blunders ?? blunders : blunders)} accent="text-app-blunder" />
      </div>
    </Card>
  );
}

function average(a: number | null, b: number | null): number | null {
  const values = [a, b].filter((value): value is number => value !== null);
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

function StripItem({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div className="min-w-0 p-4">
      <p className="truncate text-[11px] font-bold uppercase tracking-[0.12em] text-app-muted">{label}</p>
      <p className={`mt-2 font-mono text-2xl font-black ${accent}`}>{value}</p>
    </div>
  );
}
