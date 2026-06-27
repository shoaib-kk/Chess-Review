// Behavioural-pattern cards + a weakness heatmap overlaid on a board (Section 8).
import { useMemo, useState } from "react";
import { Chessboard } from "react-chessboard";
import { AlertTriangle } from "lucide-react";
import type { BehaviouralPattern } from "./types";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

// Map a pattern type to the squares it most plausibly concerns, so the heatmap
// is indicative rather than arbitrary. Returns [] for patterns with no obvious
// board region (those still show as cards).
function regionForPattern(patternType: string): string[] {
  const t = patternType.toLowerCase();
  if (t.includes("back_rank")) {
    return ["a1", "b1", "c1", "d1", "e1", "f1", "g1", "h1", "a8", "b8", "c8", "d8", "e8", "f8", "g8", "h8"];
  }
  if (t.includes("kingside") || t.includes("overextension")) {
    return ["f2", "g2", "h2", "f3", "g3", "h3", "f7", "g7", "h7", "f6", "g6", "h6"];
  }
  if (t.includes("hanging") || t.includes("fork") || t.includes("tactical") || t.includes("pin")) {
    return ["d4", "e4", "d5", "e5", "c4", "f4", "c5", "f5"];
  }
  return [];
}

function severityColor(severity: number): string {
  // teal -> amber -> red as severity climbs.
  if (severity >= 0.66) return "rgba(239,68,68,0.42)";
  if (severity >= 0.33) return "rgba(245,158,11,0.40)";
  return "rgba(94,234,212,0.32)";
}

export function WeaknessBoard({ patterns }: { patterns: BehaviouralPattern[] }) {
  const [selected, setSelected] = useState(0);
  const withRegions = useMemo(
    () => patterns.filter((p) => regionForPattern(p.pattern_type).length > 0),
    [patterns],
  );

  const active = withRegions[selected];
  const styles = useMemo(() => {
    const out: Record<string, React.CSSProperties> = {};
    if (active) {
      const color = severityColor(active.severity_score);
      for (const sq of regionForPattern(active.pattern_type)) {
        out[sq] = { background: color, boxShadow: "inset 0 0 0 2px rgba(239,68,68,0.25)" };
      }
    }
    return out;
  }, [active]);

  if (withRegions.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-app-subtle">
        No board-localisable weaknesses detected.
      </p>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-[minmax(0,300px)_1fr]">
      <div className="mx-auto w-full max-w-[300px]">
        <Chessboard
          position={START_FEN}
          arePiecesDraggable={false}
          boardOrientation="white"
          customSquareStyles={styles}
          customBoardStyle={{ borderRadius: 8 }}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        {withRegions.map((p, i) => (
          <button
            key={p.pattern_type}
            onClick={() => setSelected(i)}
            className={`rounded-lg border px-3 py-2 text-left text-sm transition ${
              i === selected
                ? "border-app-accentLine bg-app-accentSoft text-app-text"
                : "border-app-border text-app-muted hover:bg-white/[0.04]"
            }`}
          >
            <span className="font-medium">{p.label}</span>
            <span className="ml-2 text-xs text-app-subtle">
              {(p.confidence * 100).toFixed(0)}% conf
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

export function PatternCard({ pattern }: { pattern: BehaviouralPattern }) {
  const sev = pattern.severity_score;
  const tone =
    sev >= 0.66 ? "text-app-blunder" : sev >= 0.33 ? "text-amber-400" : "text-app-accent";
  return (
    <div className="rounded-xl border border-app-border bg-app-raised/60 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className={`h-4 w-4 ${tone}`} strokeWidth={2} />
          <h4 className="text-sm font-semibold text-app-text">{pattern.label}</h4>
        </div>
        <span className="shrink-0 rounded-full bg-white/[0.06] px-2 py-0.5 text-[11px] text-app-subtle">
          {pattern.sample_count}× · {(pattern.confidence * 100).toFixed(0)}%
        </span>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-app-muted">{pattern.description}</p>
      <div className="mt-3 flex gap-3 text-[11px] text-app-subtle">
        <Meter label="Severity" value={pattern.severity_score} />
        <Meter label="Frequency" value={pattern.frequency_score} />
      </div>
    </div>
  );
}

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex-1">
      <div className="mb-1 flex justify-between">
        <span>{label}</span>
        <span>{(value * 100).toFixed(0)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="h-full rounded-full bg-app-accent" style={{ width: `${value * 100}%` }} />
      </div>
    </div>
  );
}
