import type { GameSummary } from "../types";
import { Button } from "./ui/Button";
import { ProgressRing } from "./ui/ProgressRing";
import { Surface } from "./ui/Surface";

interface SummaryStripProps {
  summary: GameSummary;
  reviewMyMovesOnly?: boolean;
  onReviewMyMovesOnlyChange?: (value: boolean) => void;
  onImportGame?: () => void;
}

function fmt(value: number | null, suffix = "") {
  return value === null ? "—" : `${value.toFixed(1)}${suffix}`;
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
    ? `${summary.user_username} as ${summary.user_color} · ${summary.result}`
    : `${summary.white_player} vs ${summary.black_player} · ${summary.result}`;
  const accuracyLabel = summary.user_username ? "Your accuracy" : "Game accuracy";
  const accentColor = accuracy != null && accuracy >= 80 ? "#5cb585" : accuracy != null && accuracy >= 60 ? "#c8a15a" : "#dc8a45";

  return (
    <Surface className="flex flex-col gap-5 p-5 sm:p-6">
      {/* Identity + controls */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div className="min-w-0">
          {summary.eco_code && (
            <span className="mb-1.5 inline-block rounded-md border border-app-border bg-app-bgInset px-2 py-0.5 font-mono text-[11px] font-semibold text-app-accent">
              {summary.eco_code}
            </span>
          )}
          <h1 className="truncate text-xl font-semibold tracking-tight text-app-text">{opening}</h1>
          <p className="mt-1 truncate text-sm text-app-muted">{perspective}</p>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          {onReviewMyMovesOnlyChange && summary.user_username && (
            <label className="flex cursor-pointer items-center gap-2 text-sm text-app-muted">
              <input
                type="checkbox"
                className="h-4 w-4 accent-app-accent"
                checked={reviewMyMovesOnly}
                onChange={(event) => onReviewMyMovesOnlyChange(event.target.checked)}
              />
              My moves only
            </label>
          )}
          {onImportGame && (
            <Button variant="secondary" size="sm" onClick={onImportGame}>
              Import another
            </Button>
          )}
        </div>
      </div>

      {/* Metrics: featured accuracy ring leads, supporting stats follow */}
      <div className="flex flex-col gap-5 border-t border-app-border pt-5 lg:flex-row lg:items-center lg:gap-7">
        <div
          className="flex shrink-0 items-center gap-4 lg:pr-7"
          title="Accuracy estimates how often strong moves were found, from this perspective."
        >
          <ProgressRing value={accuracy ?? 0} size={76} strokeWidth={7} color={accentColor}>
            <span className="nums text-lg font-semibold text-app-text">{accuracy != null ? accuracy.toFixed(0) : "—"}</span>
          </ProgressRing>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-subtle">{accuracyLabel}</div>
            <div className="mt-1 nums text-3xl font-semibold leading-none tracking-tightest text-app-text">{fmt(accuracy, "%")}</div>
          </div>
        </div>

        <div className="grid flex-1 grid-cols-3 gap-y-4 sm:grid-cols-5 lg:border-l lg:border-app-border lg:pl-7">
          <StatTile label="White" value={fmt(summary.white_accuracy, "%")} title="White's review accuracy." />
          <StatTile label="Black" value={fmt(summary.black_accuracy, "%")} title="Black's review accuracy." />
          <StatTile label="Inaccuracies" value={String(inaccuracies)} tone="warning" title="Small missed chances — marked ?!" />
          <StatTile label="Mistakes" value={String(mistakes)} tone="mistake" title="Notable evaluation swings — marked ?" />
          <StatTile label="Blunders" value={String(blunders)} tone="blunder" title="Critical errors — marked ??" />
        </div>
      </div>
    </Surface>
  );
}

function StatTile({
  label,
  value,
  tone = "neutral",
  title,
}: {
  label: string;
  value: string;
  tone?: "neutral" | "warning" | "mistake" | "blunder";
  title?: string;
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
    <div title={title}>
      <div className="truncate text-[10px] font-semibold uppercase tracking-[0.14em] text-app-subtle">{label}</div>
      <div className={`mt-1 nums text-lg font-semibold ${valueTone}`}>{value}</div>
    </div>
  );
}
