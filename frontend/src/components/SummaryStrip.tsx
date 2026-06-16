import type { GameSummary } from "../types";
import { Button } from "./ui/Button";

interface SummaryStripProps {
  summary: GameSummary;
  reviewMyMovesOnly?: boolean;
  onReviewMyMovesOnlyChange?: (value: boolean) => void;
  onImportGame?: () => void;
}

function fmt(value: number | null, suffix = "") {
  return value === null ? "-" : `${value.toFixed(1)}${suffix}`;
}

function average(a: number | null, b: number | null): number | null {
  const values = [a, b].filter((value): value is number => value !== null);
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}

export function SummaryStrip({
  summary,
  reviewMyMovesOnly = false,
  onReviewMyMovesOnlyChange,
  onImportGame,
}: SummaryStripProps) {
  const inaccuracies = summary.user_username
    ? summary.user_inaccuracies ?? summary.white_inaccuracies + summary.black_inaccuracies
    : summary.white_inaccuracies + summary.black_inaccuracies;
  const mistakes = summary.user_username
    ? summary.user_mistakes ?? summary.white_mistakes + summary.black_mistakes
    : summary.white_mistakes + summary.black_mistakes;
  const blunders = summary.user_username
    ? summary.user_blunders ?? summary.white_blunders + summary.black_blunders
    : summary.white_blunders + summary.black_blunders;
  const accuracy = summary.user_username
    ? summary.user_accuracy
    : average(summary.white_accuracy, summary.black_accuracy);
  const opening = summary.opening_name
    ? `${summary.opening_name}${summary.eco_code ? ` (${summary.eco_code})` : ""}`
    : `${summary.white_player} vs ${summary.black_player}`;
  const perspective = summary.user_username
    ? `${summary.user_username} as ${summary.user_color}`
    : summary.result;

  return (
    <section className="flex flex-col justify-between gap-5 bg-app-bg pb-6 pt-1">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h1 className="text-xl font-semibold tracking-tight text-app-text">Chess Review</h1>
            <span className="truncate text-sm text-app-muted">{perspective}</span>
          </div>
          <p className="mt-1 truncate text-base font-medium text-app-text">{opening}</p>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          {onReviewMyMovesOnlyChange && summary.user_username && (
            <label className="flex items-center gap-2 text-sm text-app-muted">
              <input
                type="checkbox"
                className="h-4 w-4 accent-app-accent"
                checked={reviewMyMovesOnly}
                onChange={(event) => onReviewMyMovesOnlyChange(event.target.checked)}
              />
              My moves
            </label>
          )}
          {onImportGame && (
            <Button variant="secondary" size="sm" onClick={onImportGame}>
              Import Game
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <StatTile label={summary.white_player} value={fmt(summary.white_accuracy, "%")} />
        <StatTile label={summary.black_player} value={fmt(summary.black_accuracy, "%")} />
        <StatTile label="Overall" value={fmt(accuracy, "%")} />
        <StatTile label="Inaccuracies" value={String(inaccuracies)} tone="warning" />
        <StatTile label="Mistakes" value={String(mistakes)} tone="mistake" />
        <StatTile label="Blunders" value={String(blunders)} tone="blunder" />
      </div>
    </section>
  );
}

function StatTile({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "warning" | "mistake" | "blunder";
}) {
  const valueTone =
    tone === "warning"
      ? "text-app-warning"
      : tone === "mistake"
        ? "text-app-mistake"
        : tone === "blunder"
          ? "text-app-blunder"
          : "text-app-text";

  return (
    <div className="rounded-lg border border-app-border bg-app-panel/60 px-3 py-2.5 shadow-card">
      <div className="truncate text-[10px] font-semibold uppercase tracking-[0.18em] text-app-muted">{label}</div>
      <div className={`mt-1 font-mono text-lg font-semibold ${valueTone}`}>{value}</div>
    </div>
  );
}
