import { Chessboard } from "react-chessboard";
import type { GameSummary, MoveAnalysis, MoveClassification } from "../types";
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

const annotationSymbols: Record<MoveClassification, string> = {
  Excellent: "",
  Inaccuracy: "?!",
  Mistake: "?",
  Blunder: "??",
};

const annotationStyles: Record<MoveClassification, { backgroundColor: string; color: string }> = {
  Excellent: { backgroundColor: "transparent", color: "inherit" },
  Inaccuracy: { backgroundColor: "#dcdcaa", color: "#1e1e1e" },
  Mistake: { backgroundColor: "#ce9178", color: "#1e1e1e" },
  Blunder: { backgroundColor: "#f14c4c", color: "#ffffff" },
};

function squareOverlayPosition(square: string, flipped: boolean) {
  const file = square.charCodeAt(0) - 97;
  const rank = Number(square[1]) - 1;
  const boardFile = flipped ? 7 - file : file;
  const boardRank = flipped ? rank : 7 - rank;

  return {
    left: `${((boardFile + 0.82) / 8) * 100}%`,
    top: `${((boardRank + 0.18) / 8) * 100}%`,
  };
}

function mistakeSquare(move: MoveAnalysis | undefined): string | null {
  if (!move || move.classification === "Excellent") return null;
  return uciSquares(move.played_move_uci)?.[1] ?? null;
}

function moveLabel(move: MoveAnalysis | undefined) {
  if (!move) return "Starting position";
  return `${move.move_number}${move.color === "White" ? "." : "..."} ${move.move_played}`;
}

function evalWhitePov(move: MoveAnalysis | undefined): number | null {
  if (!move?.eval_after && move?.eval_after !== 0) return null;
  return move.color === "White" ? -move.eval_after : move.eval_after;
}

function evalBarPercent(evalCp: number | null) {
  if (evalCp === null) return 50;
  if (Math.abs(evalCp) >= 100000) return evalCp > 0 ? 100 : 0;
  const pawns = evalCp / 100;
  return Math.max(0, Math.min(100, 50 + pawns * 8));
}

function evalLabel(evalCp: number | null) {
  if (evalCp === null) return "0.00";
  if (Math.abs(evalCp) >= 100000) return evalCp > 0 ? "Mate" : "-Mate";
  const pawns = evalCp / 100;
  return `${pawns > 0 ? "+" : ""}${pawns.toFixed(2)}`;
}

function evalLeader(evalCp: number | null) {
  if (evalCp === null || Math.abs(evalCp) < 1) return "equal";
  return evalCp > 0 ? "white" : "black";
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
  const currentEval = evalWhitePov(move);
  const whitePercent = evalBarPercent(currentEval);
  const leader = evalLeader(currentEval);
  const played = uciSquares(move?.played_move_uci ?? null);
  const best = uciSquares(move?.best_move_uci ?? null);
  const highlightedSquare = mistakeSquare(move);
  const annotationSquare = move && annotationSymbols[move.classification] ? played?.[1] : null;

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
    played ? [played[0], played[1], "#007acc"] : null,
    best && move?.best_move_uci !== move?.played_move_uci ? [best[0], best[1], "#89d185"] : null,
  ].filter(Boolean);

  const customSquareStyles = highlightedSquare
    ? {
        [highlightedSquare]: {
          background:
            move?.classification === "Blunder"
              ? "radial-gradient(circle, rgba(241,76,76,0.68) 0%, rgba(241,76,76,0.22) 72%)"
              : move?.classification === "Mistake"
                ? "radial-gradient(circle, rgba(206,145,120,0.68) 0%, rgba(206,145,120,0.22) 72%)"
                : "radial-gradient(circle, rgba(220,220,170,0.68) 0%, rgba(220,220,170,0.2) 72%)",
        },
      }
    : {};

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-col gap-4 px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
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
        <div className="mx-auto grid max-w-[730px] grid-cols-[28px_minmax(0,680px)] gap-3">
          <div className="relative overflow-hidden bg-[#111111]" aria-label={`Evaluation ${evalLabel(currentEval)}`}>
            <div className="absolute inset-x-0 bottom-0 bg-[#d4d4d4] transition-all duration-200" style={{ height: `${whitePercent}%` }} />
            <div className="absolute inset-x-0 top-0 bg-[#1e1e1e] transition-all duration-200" style={{ height: `${100 - whitePercent}%` }} />
            {leader === "black" && (
              <div className="absolute inset-x-0 top-1 text-center font-mono text-[10px] font-medium text-[#d4d4d4]">
                {evalLabel(currentEval)}
              </div>
            )}
            {leader === "white" && (
              <div className="absolute inset-x-0 bottom-1 text-center font-mono text-[10px] font-medium text-[#1e1e1e]">
                {evalLabel(currentEval)}
              </div>
            )}
            {leader === "equal" && (
              <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-center font-mono text-[10px] font-medium text-[#d4d4d4] mix-blend-difference">
                {evalLabel(currentEval)}
              </div>
            )}
          </div>
          <div className="chessboard-animated relative">
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
            {move && annotationSquare && (
              <div
                className="pointer-events-none absolute z-10 grid h-5 w-5 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full font-mono text-[9px] font-medium leading-none opacity-100"
                style={{
                  ...squareOverlayPosition(annotationSquare, flipped),
                  ...annotationStyles[move.classification],
                }}
                aria-label={move.classification}
              >
                {annotationSymbols[move.classification]}
              </div>
            )}
          </div>
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
