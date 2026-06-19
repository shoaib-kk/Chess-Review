interface WinLossBarProps {
  wins: number;
  draws: number;
  losses: number;
  className?: string;
  /** Show the W / D / L legend underneath. */
  showLegend?: boolean;
}

/** A segmented win / draw / loss ratio bar. */
export function WinLossBar({ wins, draws, losses, className = "", showLegend = false }: WinLossBarProps) {
  const total = Math.max(1, wins + draws + losses);
  const pct = (n: number) => `${(n / total) * 100}%`;

  return (
    <div className={className}>
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-white/5">
        <div className="h-full bg-app-good transition-all duration-700 ease-spring" style={{ width: pct(wins) }} />
        <div className="h-full bg-app-draw/50 transition-all duration-700 ease-spring" style={{ width: pct(draws) }} />
        <div className="h-full bg-app-loss transition-all duration-700 ease-spring" style={{ width: pct(losses) }} />
      </div>
      {showLegend && (
        <div className="mt-2 flex items-center gap-3 text-xs text-app-muted nums">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-app-good" />
            {wins}W
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-app-draw/60" />
            {draws}D
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-app-loss" />
            {losses}L
          </span>
        </div>
      )}
    </div>
  );
}
