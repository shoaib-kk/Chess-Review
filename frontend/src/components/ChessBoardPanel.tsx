import { Chessboard } from "react-chessboard";
import type { GameSummary, MoveAnalysis } from "../types";
import { ClassificationBadge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";

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
              ? "radial-gradient(circle, rgba(239,68,68,0.72) 0%, rgba(239,68,68,0.26) 72%)"
              : move?.classification === "Mistake"
                ? "radial-gradient(circle, rgba(249,115,22,0.72) 0%, rgba(249,115,22,0.24) 72%)"
                : "radial-gradient(circle, rgba(234,179,8,0.72) 0%, rgba(234,179,8,0.22) 72%)",
        },
      }
    : {};

  return (
    <Card className="overflow-hidden">
      <CardHeader
        title="Board"
        eyebrow="Position"
        action={<Button variant="ghost" size="sm" onClick={onFlip}>Flip board</Button>}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm text-app-text">{moveLabel(move)}</span>
          {move && <ClassificationBadge classification={move.classification} />}
        </div>
      </CardHeader>

      <div className="px-4 pb-5 sm:px-5">
        <div className="mx-auto max-w-[560px] rounded-lg bg-slate-950/55 p-3 shadow-inner ring-1 ring-app-border">
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
          <div className="grid h-9 place-items-center rounded-md bg-slate-950/70 px-2 font-mono text-xs text-app-muted ring-1 ring-app-border">
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
