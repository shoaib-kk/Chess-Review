import { Chessboard } from "react-chessboard";
import type { GameSummary, MoveAnalysis } from "../types";
import { ClassificationBadge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";

interface ChessboardPanelProps {
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

function moveLabel(move: MoveAnalysis | undefined) {
  if (!move) return "Starting position";
  return `${move.move_number}${move.color === "White" ? "." : "..."} ${move.move_played}`;
}

export function ChessboardPanel({
  summary,
  moveIndex,
  flipped,
  reviewMyMovesOnly = false,
  onFlip,
  onMoveIndexChange,
}: ChessboardPanelProps) {
  const move = moveIndex >= 0 ? summary.move_analyses[moveIndex] : undefined;
  const position = move?.fen_after ?? summary.initial_fen;
  const played = uciSquares(move?.played_move_uci ?? null);
  const best = uciSquares(move?.best_move_uci ?? null);
  const highlightedSquare = mistakeSquare(move);

  const navigationIndexes =
    reviewMyMovesOnly && summary.user_color
      ? summary.move_analyses
          .map((item, index) => (item.color === summary.user_color ? index : -2))
          .filter((index) => index >= 0)
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
              ? "radial-gradient(circle, rgba(239,68,68,0.68) 0%, rgba(239,68,68,0.22) 72%)"
              : move?.classification === "Mistake"
                ? "radial-gradient(circle, rgba(249,115,22,0.68) 0%, rgba(249,115,22,0.22) 72%)"
                : "radial-gradient(circle, rgba(234,179,8,0.68) 0%, rgba(234,179,8,0.2) 72%)",
        },
      }
    : {};

  return (
    <Card className="overflow-hidden ring-1 ring-app-border/70">
      <div className="flex flex-col gap-3 border-b border-app-border/70 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-app-muted">Position</p>
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <span className="font-mono text-2xl font-medium text-app-text">{moveLabel(move)}</span>
            {move && <ClassificationBadge classification={move.classification} />}
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={onFlip}>Flip board</Button>
      </div>

      <div className="px-4 pb-5 pt-5 sm:px-5">
        <div className="chessboard-animated mx-auto max-w-[680px]">
          <Chessboard
            id={1}
            position={position}
            animationDuration={220}
            boardOrientation={flipped ? "black" : "white"}
            arePiecesDraggable={false}
            customBoardStyle={{
              overflow: "hidden",
            }}
            customDarkSquareStyle={{ backgroundColor: "#b58863" }}
            customLightSquareStyle={{ backgroundColor: "#f0d9b5" }}
            customArrows={arrows as never}
            customSquareStyles={customSquareStyles}
          />
        </div>

        <div className="mt-4 grid grid-cols-[1fr_1fr_minmax(74px,0.8fr)_1fr_1fr] gap-2">
          <Button variant="control" size="sm" onClick={() => onMoveIndexChange(firstIndex)} aria-label="First move">
            First
          </Button>
          <Button
            variant="control"
            size="sm"
            onClick={() => onMoveIndexChange(reviewMyMovesOnly ? previousIndex : Math.max(-1, moveIndex - 1))}
            aria-label="Previous move"
          >
            Prev
          </Button>
          <div className="grid h-9 place-items-center bg-app-panelSecondary px-2 font-mono text-xs text-app-muted">
            {moveIndex + 1}/{summary.total_moves}
          </div>
          <Button
            variant="control"
            size="sm"
            onClick={() => onMoveIndexChange(reviewMyMovesOnly ? nextIndex : Math.min(summary.total_moves - 1, moveIndex + 1))}
            aria-label="Next move"
          >
            Next
          </Button>
          <Button variant="control" size="sm" onClick={() => onMoveIndexChange(lastIndex)} aria-label="Last move">
            Last
          </Button>
        </div>
      </div>
    </Card>
  );
}
