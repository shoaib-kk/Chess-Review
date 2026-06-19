import { useEffect, useState } from "react";
import { Check, Cpu } from "lucide-react";
import type { AnalysisMode } from "../types";
import { ChessGlyph } from "./ui/ChessGlyph";
import { Surface } from "./ui/Surface";

interface AnalysisProgressProps {
  /** Estimated number of plies (half-moves) in the game, used to pace the bar. */
  plies?: number;
  mode?: AnalysisMode;
  /** Optional override for the headline (e.g. game name). */
  title?: string;
}

const PER_PLY_MS: Record<AnalysisMode, number> = { fast: 70, normal: 200, deep: 500 };
const MODE_LABEL: Record<AnalysisMode, string> = { fast: "Quick", normal: "Standard", deep: "Thorough" };

const STEPS = [
  { key: "parse", label: "Parse moves" },
  { key: "evaluate", label: "Evaluate positions" },
  { key: "classify", label: "Classify moves" },
  { key: "report", label: "Build report" },
] as const;

function statusFor(progress: number): string {
  if (progress < 15) return "Reading the game and setting up the board…";
  if (progress < 40) return "Warming up the Stockfish engine…";
  if (progress < 72) return "Evaluating each position with the engine…";
  if (progress < 92) return "Spotting blunders and classifying every move…";
  return "Compiling your accuracy report…";
}

/**
 * A reassuring, time-estimated progress card shown while a game is analysed.
 * The backend analysis is a single blocking request with no progress stream, so
 * the bar is paced from the game's length and depth and eases toward ~96%; the
 * appearance of the finished review is the real completion signal.
 */
export function AnalysisProgress({ plies = 0, mode = "normal", title }: AnalysisProgressProps) {
  const [progress, setProgress] = useState(4);

  const estPlies = plies > 0 ? plies : 60;
  const estDuration = 1400 + estPlies * PER_PLY_MS[mode];

  useEffect(() => {
    const start = performance.now();
    const tau = Math.max(2600, estDuration / 3);
    const id = window.setInterval(() => {
      const elapsed = performance.now() - start;
      // Decelerating curve that approaches — but never reaches — 96%.
      const target = 4 + 92 * (1 - Math.exp(-elapsed / tau));
      setProgress((current) => (target > current ? target : current));
    }, 110);
    return () => window.clearInterval(id);
  }, [estDuration]);

  const activeStep = progress < 15 ? 0 : progress < 72 ? 1 : progress < 92 ? 2 : 3;
  const positions = plies > 0 ? plies : null;

  return (
    <Surface
      variant="raised"
      className="relative mx-auto w-full max-w-xl animate-pop-in overflow-hidden p-7"
      role="status"
      aria-live="polite"
    >
      <div className="pointer-events-none absolute -right-6 -top-8 text-[120px] leading-none text-app-accent/[0.05]">
        <ChessGlyph piece="knight" />
      </div>

      <div className="flex items-center gap-3">
        <span className="relative grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-app-accentLine bg-accent-sheen text-app-accent">
          <span className="absolute inset-0 animate-ring-pulse rounded-xl ring-1 ring-app-accentLine" />
          <Cpu className="h-5 w-5" strokeWidth={2} />
        </span>
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold tracking-tight text-app-text">
            {title ?? "Analyzing your game"}
          </h2>
          <p className="mt-0.5 truncate text-sm text-app-muted">
            {positions ? `${positions} positions` : "Your game"} · {MODE_LABEL[mode]} depth
          </p>
        </div>
        <span className="ml-auto shrink-0 nums text-2xl font-semibold tracking-tightest text-app-text">
          {Math.round(progress)}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="mt-6 h-2.5 w-full overflow-hidden rounded-full bg-app-bgInset ring-1 ring-inset ring-app-border">
        <div
          className="relative h-full rounded-full bg-gradient-to-r from-app-accent/80 to-app-accent transition-[width] duration-300 ease-out"
          style={{ width: `${progress}%` }}
          role="progressbar"
          aria-valuenow={Math.round(progress)}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <span className="absolute inset-0 overflow-hidden rounded-full">
            <span className="absolute inset-y-0 -left-full w-full animate-shimmer bg-gradient-to-r from-transparent via-white/25 to-transparent" />
          </span>
        </div>
      </div>

      <p className="mt-3 text-sm text-app-muted">{statusFor(progress)}</p>

      {/* Step indicator */}
      <ol className="mt-6 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        {STEPS.map((step, i) => {
          const done = i < activeStep;
          const current = i === activeStep;
          return (
            <li
              key={step.key}
              className={`flex items-center gap-2 rounded-lg border px-2.5 py-2 text-xs font-medium transition ${
                done
                  ? "border-app-good/30 bg-app-good/10 text-app-good"
                  : current
                    ? "border-app-accentLine bg-app-accentSoft text-app-text"
                    : "border-app-border bg-app-bgInset text-app-subtle"
              }`}
            >
              <span
                className={`grid h-4 w-4 shrink-0 place-items-center rounded-full text-[10px] ${
                  done
                    ? "bg-app-good/20"
                    : current
                      ? "bg-app-accent text-app-accentFg"
                      : "bg-white/5 text-app-subtle"
                }`}
              >
                {done ? <Check className="h-3 w-3" strokeWidth={3} /> : current ? "" : i + 1}
                {current && <span className="h-1.5 w-1.5 animate-ring-pulse rounded-full bg-app-accentFg" />}
              </span>
              <span className="truncate">{step.label}</span>
            </li>
          );
        })}
      </ol>

      <p className="mt-5 text-center text-xs text-app-faint">
        Longer games and deeper analysis take more time — this won't freeze.
      </p>
    </Surface>
  );
}
