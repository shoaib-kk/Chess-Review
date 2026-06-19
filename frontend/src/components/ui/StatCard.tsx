import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Surface } from "./Surface";
import { Delta } from "./Delta";

interface StatCardProps {
  label: string;
  value: ReactNode;
  /** Small unit shown after the value (e.g. "%"). */
  unit?: string;
  icon?: LucideIcon;
  /** Signed change rendered as a coloured pill. */
  delta?: number | null;
  deltaSuffix?: string;
  invertDelta?: boolean;
  /** Optional caption under the value. */
  caption?: string;
  /** Right-aligned visual (sparkline, ring, bar). */
  visual?: ReactNode;
  className?: string;
}

/**
 * A compact metric card: eyebrow label + icon, a large tabular value, an
 * optional trend pill, and room for a small visual on the right.
 */
export function StatCard({
  label,
  value,
  unit,
  icon: Icon,
  delta,
  deltaSuffix = "",
  invertDelta = false,
  caption,
  visual,
  className = "",
}: StatCardProps) {
  return (
    <Surface className={`flex flex-col justify-between gap-3 p-4 ${className}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-app-subtle">{label}</span>
        {Icon && <Icon className="h-4 w-4 text-app-faint" strokeWidth={2} />}
      </div>
      <div className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-baseline gap-1">
            <span className="text-3xl font-semibold leading-none tracking-tightest text-app-text nums">{value}</span>
            {unit && <span className="text-base font-medium text-app-muted">{unit}</span>}
          </div>
          <div className="mt-2 flex items-center gap-2">
            {delta !== undefined && <Delta value={delta} suffix={deltaSuffix} invert={invertDelta} />}
            {caption && <span className="truncate text-xs text-app-muted">{caption}</span>}
          </div>
        </div>
        {visual && <div className="shrink-0">{visual}</div>}
      </div>
    </Surface>
  );
}
