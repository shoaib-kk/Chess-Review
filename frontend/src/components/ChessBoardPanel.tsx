import { Chessboard } from "react-chessboard";
import type { GameSummary, MoveAnalysis } from "../types";

interface ChessBoardPanelProps {
  summary: GameSummary;
  moveIndex: number;
  flipped: boolean;
  reviewMyMovesOnly?: boolean;
  onFlip: () => void;
  onMoveIndexChange: (index: number) => void;
}

function uciSquares(uci: string | null): [string, string] | null {
  if (!uci || uci.length < 4) return null;
  return [uci.slice(0, 2), uci.slice(2, 4)];
}

function mistakeSquare(move: MoveAnalysis | undefined): string | null {
  if (!move || move.classification === "Excellent") return null;
  return uciSquares(move.played_move_uci)?.[1] ?? null;
}

export function ChessBoardPanel({
  summary,
  moveIndex,
  flipped,
  reviewMyMovesOnly = false,
  onFlip,
  onMoveIndexChange,
}: ChessBoardPanelProps) {
  const move = moveIndex >= 0 ? summary.move_analyses[moveIndex] : undefined;
  const position = move?.fen_after ?? summary.initial_fen;
  const played = uciSquares(move?.played_move_uci ?? null);
  const best = uciSquares(move?.best_move_uci ?? null);
  const highlightedSquare = mistakeSquare(move);
  const navigationIndexes = reviewMyMovesOnly && summary.user_color
    ? summary.move_analyses
        .map((item, index) => (item.color === summary.user_color ? index : -2))
        .filter((index) => index >= -1)
    : summary.move_analyses.map((_, index) => index);

  const firstIndex = reviewMyMovesOnly ? navigationIndexes[0] ?? -1 : -1;
  const lastIndex = navigationIndexes[navigationIndexes.length - 1] ?? summary.total_moves - 1;
  const previousIndex = [...navigationIndexes].reverse().find((index) => index < moveIndex) ?? firstIndex;
  const nextIndex = navigationIndexes.find((index) => index > moveIndex) ?? lastIndex;

  const arrows = [
    played ? [played[0], played[1], "#3b82f6"] : null,
    best && move?.best_move_uci !== move?.played_move_uci ? [best[0], best[1], "#22c55e"] : null,
  ].filter(Boolean);

  const customSquareStyles = highlightedSquare
    ? {
        [highlightedSquare]: {
          background:
            move?.classification === "Blunder"
              ? "radial-gradient(circle, rgba(239,68,68,0.75) 0%, rgba(239,68,68,0.28) 70%)"
              : move?.classification === "Mistake"
                ? "radial-gradient(circle, rgba(249,115,22,0.7) 0%, rgba(249,115,22,0.24) 70%)"
                : "radial-gradient(circle, rgba(250,204,21,0.7) 0%, rgba(250,204,21,0.24) 70%)",
        },
      }
    : {};

  return (
    <section className="rounded bg-app-panel p-4 shadow-panel">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Board</p>
          <p className="font-mono text-sm text-slate-200">
            {move ? `${move.move_number}${move.color === "White" ? "." : "..."} ${move.move_played}` : "Starting position"}
          </p>
        </div>
        <button className="rounded border border-white/10 px-3 py-1.5 text-sm text-slate-200 hover:border-app-accent" onClick={onFlip}>
          Flip
        </button>
      </div>

      <div className="mx-auto max-w-[520px]">
        <Chessboard
          position={position}
          boardOrientation={flipped ? "black" : "white"}
          arePiecesDraggable={false}
          customDarkSquareStyle={{ backgroundColor: "#b58863" }}
          customLightSquareStyle={{ backgroundColor: "#f0d9b5" }}
          customArrows={arrows as never}
          customSquareStyles={customSquareStyles}
        />
      </div>

      <div className="mt-4 grid grid-cols-5 gap-2">
        <button className="rounded bg-slate-900 py-2 text-sm hover:bg-slate-800" onClick={() => onMoveIndexChange(firstIndex)}>
          |&lt;
        </button>
        <button className="rounded bg-slate-900 py-2 text-sm hover:bg-slate-800" onClick={() => onMoveIndexChange(reviewMyMovesOnly ? previousIndex : Math.max(-1, moveIndex - 1))}>
          &lt;
        </button>
        <div className="grid place-items-center rounded bg-slate-950 text-sm text-slate-300">
          {moveIndex + 1}/{summary.total_moves}
        </div>
        <button className="rounded bg-slate-900 py-2 text-sm hover:bg-slate-800" onClick={() => onMoveIndexChange(reviewMyMovesOnly ? nextIndex : Math.min(summary.total_moves - 1, moveIndex + 1))}>
          &gt;
        </button>
        <button className="rounded bg-slate-900 py-2 text-sm hover:bg-slate-800" onClick={() => onMoveIndexChange(lastIndex)}>
          &gt;|
        </button>
      </div>
    </section>
  );
}
