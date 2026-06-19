import { useState } from "react";
import { Chessboard } from "react-chessboard";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, FlipVertical2, Swords } from "lucide-react";
import type { GameSummary, MoveAnalysis } from "../types";
import { classificationMeta } from "../utils/classification";
import { isMateScore, mateInMoves } from "../utils/evalFormat";
import { ExploreBoard } from "./ExploreBoard";
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

function hexToRgba(hex: string, alpha: number): string {
  const value = hex.replace("#", "");
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

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
  if (!move || !classificationMeta(move.classification).isError) return null;
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
  if (isMateScore(evalCp)) return evalCp > 0 ? 100 : 0;
  const pawns = evalCp / 100;
  return Math.max(0, Math.min(100, 50 + pawns * 8));
}

function evalLabel(evalCp: number | null) {
  if (evalCp === null) return "0.00";
  if (isMateScore(evalCp)) return `${evalCp > 0 ? "" : "-"}M${mateInMoves(evalCp)}`;
  const pawns = evalCp / 100;
  return `${pawns > 0 ? "+" : ""}${pawns.toFixed(2)}`;
}

function evalDescription(evalCp: number | null) {
  if (evalCp === null || Math.abs(evalCp) < 30) return "Equal";
  if (isMateScore(evalCp)) {
    return evalCp > 0 ? `White has mate in ${mateInMoves(evalCp)}` : `Black has mate in ${mateInMoves(evalCp)}`;
  }
  if (evalCp > 0) return evalCp > 300 ? "White is winning" : "White is better";
  return evalCp < -300 ? "Black is winning" : "Black is better";
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
  const [exploreFen, setExploreFen] = useState<string | null>(null);

  const move = moveIndex >= 0 ? summary.move_analyses[moveIndex] : undefined;
  const position = move?.fen_after ?? summary.initial_fen;

  if (exploreFen) {
    return (
      <ExploreBoard
        fen={exploreFen}
        orientation={flipped ? "black" : "white"}
        onExit={() => setExploreFen(null)}
        title={`Play out from ${moveLabel(move)}`}
      />
    );
  }

  const currentEval = evalWhitePov(move);
  const whitePercent = evalBarPercent(currentEval);
  const leader = evalLeader(currentEval);
  const played = uciSquares(move?.played_move_uci ?? null);
  const best = uciSquares(move?.best_move_uci ?? null);
  const highlightedSquare = mistakeSquare(move);
  const meta = move ? classificationMeta(move.classification) : null;
  const annotationSquare = meta && meta.boardSymbol ? played?.[1] : null;

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
    played ? [played[0], played[1], "#c8a15a"] : null,
    best && move?.best_move_uci !== move?.played_move_uci ? [best[0], best[1], "#5cb585"] : null,
  ].filter(Boolean);

  const customSquareStyles =
    highlightedSquare && meta
      ? {
          [highlightedSquare]: {
            background: `radial-gradient(circle, ${hexToRgba(meta.color, 0.68)} 0%, ${hexToRgba(meta.color, 0.22)} 72%)`,
          },
        }
      : {};

  return (
    <Card>
      <div className="flex flex-col gap-4 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">Position</p>
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <span className="font-mono text-2xl font-semibold text-app-text">{moveLabel(move)}</span>
            {move && <ClassificationBadge classification={move.classification} />}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setExploreFen(position)}>
            <Swords className="h-4 w-4" />
            Play from here
          </Button>
          <Button variant="ghost" size="sm" onClick={onFlip}>
            <FlipVertical2 className="h-4 w-4" />
            Flip board
          </Button>
        </div>
      </div>

      <div>
        <div className="mx-auto grid max-w-[730px] grid-cols-[28px_minmax(0,680px)] gap-3">
          <div
            className="relative overflow-hidden rounded-lg border border-app-border bg-[#0a0a0c] ring-1 ring-inset ring-white/5"
            aria-label={`Evaluation: ${evalDescription(currentEval)}`}
            title={`${evalDescription(currentEval)} (${evalLabel(currentEval)})`}
          >
            <div className="absolute inset-x-0 bottom-0 bg-[#ededed] transition-all duration-300 ease-out" style={{ height: `${whitePercent}%` }} />
            <div className="absolute inset-x-0 top-0 bg-[#0a0a0c] transition-all duration-300 ease-out" style={{ height: `${100 - whitePercent}%` }} />
            <div className="absolute left-1/2 top-1/2 h-px w-full -translate-x-1/2 -translate-y-1/2 bg-app-accent/40" />
            {leader === "black" && (
              <div className="absolute inset-x-0 top-1 text-center font-mono text-[10px] font-semibold text-[#ededed]">
                {evalLabel(currentEval)}
              </div>
            )}
            {leader === "white" && (
              <div className="absolute inset-x-0 bottom-1 text-center font-mono text-[10px] font-semibold text-[#0a0a0c]">
                {evalLabel(currentEval)}
              </div>
            )}
            {leader === "equal" && (
              <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-center font-mono text-[10px] font-semibold text-[#ededed] mix-blend-difference">
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
            {move && meta && annotationSquare && (
              <div
                className="pointer-events-none absolute z-10 grid h-5 w-5 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full font-mono text-[9px] font-medium leading-none opacity-100"
                style={{
                  ...squareOverlayPosition(annotationSquare, flipped),
                  ...meta.annotation,
                }}
                aria-label={move.classification}
              >
                {meta.boardSymbol}
              </div>
            )}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-[1fr_1fr_minmax(74px,0.8fr)_1fr_1fr] gap-2">
          <Button variant="control" size="sm" onClick={() => onMoveIndexChange(firstIndex)} aria-label="First move">
            <ChevronsLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="control"
            size="sm"
            onClick={() => onMoveIndexChange(reviewMyMovesOnly ? previousIndex : Math.max(-1, moveIndex - 1))}
            aria-label="Previous move"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <div className="grid h-9 place-items-center rounded-lg border border-app-border bg-app-panelSecondary px-2 font-mono text-xs text-app-muted">
            {moveIndex + 1}/{summary.total_moves}
          </div>
          <Button
            variant="control"
            size="sm"
            onClick={() => onMoveIndexChange(reviewMyMovesOnly ? nextIndex : Math.min(summary.total_moves - 1, moveIndex + 1))}
            aria-label="Next move"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button variant="control" size="sm" onClick={() => onMoveIndexChange(lastIndex)} aria-label="Last move">
            <ChevronsRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </Card>
  );
}
