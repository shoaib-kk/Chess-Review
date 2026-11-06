import { Chess } from "chess.js";
import { useMemo } from "react";
import type { CSSProperties } from "react";
import { Chessboard } from "react-chessboard";
import type { ScoutSplit } from "../../types";
import { Delta } from "../ui/Delta";

export type Side = "white" | "black"; // the *opponent's* colour
export type OpenLine = (side: Side, path: string[]) => void;

export function pct(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? "–" : `${value.toFixed(digits)}%`;
}

export function evalText(cp: number | null | undefined): string {
  if (cp === null || cp === undefined) return "–";
  if (Math.abs(cp) >= 9000) return cp > 0 ? "+M" : "-M";
  const pawns = cp / 100;
  return `${pawns > 0 ? "+" : ""}${pawns.toFixed(1)}`;
}

export function lineText(path: string[]): string {
  return path.map((san, i) => (i % 2 === 0 ? `${i / 2 + 1}. ${san}` : san)).join(" ");
}

export const eyebrowCls = "text-[11px] font-semibold uppercase tracking-wider text-app-subtle";

/** Bullet list of plain-text insights. */
export function InsightList({ items, className = "" }: { items: string[]; className?: string }) {
  if (!items.length) return null;
  return (
    <ul className={`grid gap-2 ${className}`}>
      {items.map((item) => (
        <li
          key={item}
          className="rounded-lg border border-app-accentLine bg-app-accentSoft px-3 py-2 text-sm leading-relaxed text-app-text"
        >
          {item}
        </li>
      ))}
    </ul>
  );
}

/** Compact row for a ScoutSplit: label, games, bar of score, score, vs-rating delta. */
export function SplitRow({ split, extra }: { split: ScoutSplit; extra?: string }) {
  const low = split.games < 5;
  return (
    <div className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 ${low ? "opacity-60" : ""}`}>
      <div className="min-w-0">
        <div className="flex items-baseline justify-between gap-2 text-sm">
          <span className="truncate text-app-muted" title={extra}>
            {split.label}
          </span>
          <span className="nums shrink-0 text-xs text-app-faint">{split.games}g</span>
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
          <div
            className="h-full rounded-full bg-app-accent/70"
            style={{ width: `${Math.max(0, Math.min(100, split.score_pct))}%` }}
          />
        </div>
      </div>
      <div className="flex items-center justify-end gap-2">
        <span className="nums w-10 text-right text-sm font-semibold text-app-text">{pct(split.score_pct)}</span>
        <span className="w-12 text-right">
          <Delta value={split.perf_delta} invert decimals={0} />
        </span>
      </div>
    </div>
  );
}

/** Read-only board for a FEN with optional highlighted squares. */
export function MiniBoard({
  id,
  fen,
  orientation,
  squares,
}: {
  id: string;
  fen: string;
  orientation: Side;
  squares?: Record<string, CSSProperties>;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-app-border">
      <Chessboard
        id={id}
        position={fen}
        boardOrientation={orientation}
        arePiecesDraggable={false}
        animationDuration={150}
        customSquareStyles={squares}
        customDarkSquareStyle={{ backgroundColor: "#b58863" }}
        customLightSquareStyle={{ backgroundColor: "#f0d9b5" }}
      />
    </div>
  );
}

export interface Frame {
  fen: string;
  label: string;
  from?: string;
  to?: string;
}

/** Replays SAN moves from a FEN, returning one frame per position (stops at the first illegal move). */
export function useFrames(fen: string, steps: Array<{ san: string; label: string }>): Frame[] {
  const key = JSON.stringify(steps);
  return useMemo(() => {
    const frames: Frame[] = [{ fen, label: "Start" }];
    try {
      const chess = new Chess(fen);
      for (const step of JSON.parse(key) as Array<{ san: string; label: string }>) {
        const move = chess.move(step.san);
        frames.push({ fen: chess.fen(), label: step.label, from: move.from, to: move.to });
      }
    } catch {
      /* stop at the first move that does not replay */
    }
    return frames;
  }, [fen, key]);
}

export function frameSquares(frame: Frame | undefined): Record<string, CSSProperties> {
  if (!frame?.from || !frame.to) return {};
  const style = { backgroundColor: "rgba(200,161,90,0.38)" };
  return { [frame.from]: style, [frame.to]: style };
}

/** Whose turn it is in a FEN. */
export function turnOf(fen: string): Side {
  return fen.split(" ")[1] === "b" ? "black" : "white";
}
