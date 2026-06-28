import { Chess, type Square } from "chess.js";
import { useEffect, useState } from "react";
import { Chessboard } from "react-chessboard";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, CornerUpLeft, FlipVertical2, Swords, Undo2 } from "lucide-react";
import type { AnalysisLine, GameSummary, MoveAnalysis } from "../types";
import { requestEngineMove } from "../api/client";
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
  analysisLine: AnalysisLine | null;
  onAnalysisLineChange: (line: AnalysisLine | null) => void;
  onFlip: () => void;
  onMoveIndexChange: (index: number) => void;
}

/** Replay a list of SAN moves from a base FEN. Returns null on any illegal move. */
function replayLine(baseFen: string, moves: string[]): { fen: string; turn: "w" | "b" } | null {
  try {
    const game = new Chess(baseFen);
    for (const san of moves) game.move(san);
    return { fen: game.fen(), turn: game.turn() };
  } catch {
    return null;
  }
}

function lineSan(baseFen: string, moves: string[]): string {
  try {
    const game = new Chess(baseFen);
    const white = game.turn() === "w";
    const start = Number(baseFen.split(" ")[5] || "1");
    const parts: string[] = [];
    moves.forEach((san, i) => {
      const moveNo = start + Math.floor((i + (white ? 0 : 1)) / 2);
      if ((white && i % 2 === 0) || (!white && i % 2 === 1)) parts.push(`${moveNo}.`);
      else if (i === 0) parts.push(`${moveNo}...`);
      parts.push(san);
    });
    return parts.join(" ");
  } catch {
    return moves.join(" ");
  }
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
  analysisLine,
  onAnalysisLineChange,
  onFlip,
  onMoveIndexChange,
}: ChessboardPanelProps) {
  const [exploreFen, setExploreFen] = useState<string | null>(null);
  const [branchEval, setBranchEval] = useState<number | null>(null);
  const [branchThinking, setBranchThinking] = useState(false);

  const move = moveIndex >= 0 ? summary.move_analyses[moveIndex] : undefined;
  const position = move?.fen_after ?? summary.initial_fen;

  const branch = analysisLine ? replayLine(analysisLine.baseFen, analysisLine.moves) : null;
  const inAnalysis = Boolean(analysisLine && branch);
  const displayPosition = branch?.fen ?? position;

  // Live engine eval for the explored position (reuses the play endpoint, whose
  // eval_cp is the side-to-move score before its move).
  useEffect(() => {
    if (!branch) {
      setBranchEval(null);
      setBranchThinking(false);
      return;
    }
    let cancelled = false;
    setBranchThinking(true);
    requestEngineMove(branch.fen)
      .then((res) => {
        if (cancelled) return;
        const cp = res.eval_cp;
        setBranchEval(cp === null || cp === undefined ? null : branch.turn === "w" ? cp : -cp);
      })
      .catch(() => {
        if (!cancelled) setBranchEval(null);
      })
      .finally(() => {
        if (!cancelled) setBranchThinking(false);
      });
    return () => {
      cancelled = true;
    };
  }, [branch?.fen, branch?.turn]);

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

  const reviewEval = evalWhitePov(move);
  const currentEval = inAnalysis ? branchEval : reviewEval;
  const whitePercent = evalBarPercent(currentEval);
  const leader = evalLeader(currentEval);
  const played = uciSquares(move?.played_move_uci ?? null);
  const best = uciSquares(move?.best_move_uci ?? null);
  const highlightedSquare = inAnalysis ? null : mistakeSquare(move);
  const meta = move ? classificationMeta(move.classification) : null;
  const annotationSquare = !inAnalysis && meta && meta.boardSymbol ? played?.[1] : null;

  function appendMove(from: string, to: string, promotion = "q"): boolean {
    const baseFen = inAnalysis && branch ? branch.fen : position;
    let game: Chess;
    try {
      game = new Chess(baseFen);
    } catch {
      return false;
    }
    let result;
    try {
      result = game.move({ from, to, promotion });
    } catch {
      return false;
    }
    if (!result) return false;
    if (inAnalysis && analysisLine) {
      onAnalysisLineChange({ baseFen: analysisLine.baseFen, moves: [...analysisLine.moves, result.san] });
    } else {
      onAnalysisLineChange({ baseFen: position, moves: [result.san] });
    }
    return true;
  }

  function isPromotionDrop(from: string, to: string): boolean {
    const baseFen = inAnalysis && branch ? branch.fen : position;
    try {
      const piece = new Chess(baseFen).get(from as Square);
      if (!piece || piece.type !== "p") return false;
      return (piece.color === "w" && to[1] === "8") || (piece.color === "b" && to[1] === "1");
    } catch {
      return false;
    }
  }

  function onPieceDrop(source: string, target: string): boolean {
    if (isPromotionDrop(source, target)) return false; // handled by promotion dialog
    return appendMove(source, target);
  }

  function onPromotionPieceSelect(piece?: string, from?: string, to?: string): boolean {
    if (!piece || !from || !to) return false;
    return appendMove(from, to, piece[1].toLowerCase());
  }

  function takeBackBranch() {
    if (!analysisLine) return;
    if (analysisLine.moves.length <= 1) onAnalysisLineChange(null);
    else onAnalysisLineChange({ baseFen: analysisLine.baseFen, moves: analysisLine.moves.slice(0, -1) });
  }

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

  const arrows = inAnalysis
    ? []
    : [
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
            {inAnalysis ? (
              <span className="rounded-full bg-app-accent/15 px-2 py-0.5 font-mono text-[11px] font-semibold text-app-accent">
                Analysis{branchThinking ? " · …" : ""}
              </span>
            ) : (
              move && <ClassificationBadge classification={move.classification} />
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setExploreFen(displayPosition)}>
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
              position={displayPosition}
              animationDuration={220}
              boardOrientation={flipped ? "black" : "white"}
              arePiecesDraggable
              onPieceDrop={onPieceDrop}
              onPromotionPieceSelect={onPromotionPieceSelect}
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

        {inAnalysis && analysisLine ? (
          <div className="mt-4 rounded-lg border border-app-accent/30 bg-app-accent/5 px-3 py-2.5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-app-accent">Exploring line</p>
                <p className="mt-1 break-words font-mono text-xs leading-5 text-app-text">
                  {lineSan(analysisLine.baseFen, analysisLine.moves)}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button variant="control" size="sm" onClick={takeBackBranch} aria-label="Take back one move">
                  <Undo2 className="h-4 w-4" />
                </Button>
                <Button variant="secondary" size="sm" onClick={() => onAnalysisLineChange(null)}>
                  <CornerUpLeft className="h-4 w-4" />
                  Back to game
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <p className="mt-4 text-center text-xs text-app-faint">Drag a piece to explore a line — the eval updates live.</p>
        )}

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
