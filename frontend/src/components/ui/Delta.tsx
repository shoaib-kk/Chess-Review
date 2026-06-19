import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

interface DeltaProps {
  /** Signed change. Positive = improvement (green) unless `invert`. */
  value: number | null | undefined;
  /** Suffix appended to the number, e.g. "%" or "pts". */
  suffix?: string;
  /** Treat negative as good (e.g. cp loss, blunders). */
  invert?: boolean;
  /** Decimals shown. */
  decimals?: number;
  className?: string;
}

/** A compact, colour-coded trend pill: ▲ +2.1 / ▼ -0.4 / — flat. */
export function Delta({ value, suffix = "", invert = false, decimals = 1, className = "" }: DeltaProps) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return null;
  }

  const rounded = Number(value.toFixed(decimals));
  const positive = invert ? rounded < 0 : rounded > 0;
  const negative = invert ? rounded > 0 : rounded < 0;
  const flat = rounded === 0;

  const tone = flat
    ? "text-app-subtle bg-white/5"
    : positive
      ? "text-app-good bg-app-good/10"
      : "text-app-blunder bg-app-blunder/10";

  const Icon = flat ? Minus : negative ? ArrowDownRight : ArrowUpRight;
  const sign = rounded > 0 ? "+" : "";

  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-semibold nums ${tone} ${className}`}
    >
      <Icon className="h-3 w-3" strokeWidth={2.5} />
      {sign}
      {rounded.toFixed(decimals)}
      {suffix}
    </span>
  );
}
