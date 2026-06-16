import { Chess, type Square } from "chess.js";
import { useRef, useState } from "react";
import { Chessboard } from "react-chessboard";
import { ChevronLeft, FlipVertical2, RotateCcw, Swords, Undo2 } from "lucide-react";
import { apiErrorMessage, requestEngineMove } from "../api/client";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";

type Mode = "free" | "engine";

const SKILL_LEVELS: { label: string; value: number }[] = [
  { label: "Easy", value: 2 },
  { label: "Medium", value: 8 },
  { label: "Hard", value: 14 },
  { label: "Max", value: 20 },
];

interface ExploreBoardProps {
  /** Position to start playing out from. */
  fen: string;
  /** Initial board orientation. */
  orientation: "white" | "black";
  /** Return to the normal review / puzzle view. */
  onExit: () => void;
  title?: string;
}

/**
 * Interactive "play out the position" board, shared by game review and puzzles.
 *
 * Free mode: drag any piece for either side to explore lines (legal moves only).
 * Engine mode: you play the side to move; Stockfish replies via /play/move.
 */
export function ExploreBoard({ fen, orientation, onExit, title = "Play out the position" }: ExploreBoardProps) {
  const gameRef = useRef(new Chess(fen));
  // In engine mode the human plays whichever side was to move when engine mode
  // was switched on.
  const humanColorRef = useRef<"w" | "b">(gameRef.current.turn());

  const [position, setPosition] = useState(fen);
  const [history, setHistory] = useState<string[]>([]);
  const [mode, setMode] = useState<Mode>("free");
  const [skillLevel, setSkillLevel] = useState(8);
  const [boardOrientation, setBoardOrientation] = useState(orientation);
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const game = gameRef.current;

  function sync() {
    setPosition(game.fen());
    setHistory(game.history());
  }

  async function engineReply() {
    if (mode !== "engine" || game.isGameOver() || game.turn() === humanColorRef.current) return;
    setThinking(true);
    setError(null);
    try {
      const res = await requestEngineMove(game.fen(), { skillLevel });
      if (res.best_move_san) {
        game.move(res.best_move_san);
        sync();
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setThinking(false);
    }
  }

  function makeMove(from: string, to: string, promotion = "q"): boolean {
    if (thinking || game.isGameOver()) return false;
    if (mode === "engine" && game.turn() !== humanColorRef.current) return false;
    try {
      const result = game.move({ from, to, promotion });
      if (!result) return false;
    } catch {
      return false; // illegal move
    }
    sync();
    void engineReply();
    return true;
  }

  function isPromotion(from: string, to: string): boolean {
    const piece = game.get(from as Square);
    if (!piece || piece.type !== "p") return false;
    return (piece.color === "w" && to[1] === "8") || (piece.color === "b" && to[1] === "1");
  }

  function onPieceDrop(source: string, target: string): boolean {
    // Promotions are routed through the promotion dialog (onPromotionPieceSelect).
    if (isPromotion(source, target)) return false;
    return makeMove(source, target);
  }

  function onPromotionPieceSelect(piece?: string, from?: string, to?: string): boolean {
    // `piece` looks like "wQ" / "bN"; chess.js wants the lowercase piece letter.
    if (!piece || !from || !to) return false;
    return makeMove(from, to, piece[1].toLowerCase());
  }

  function takeBack() {
    if (thinking) return;
    game.undo();
    // In engine mode, also undo the engine's reply so it's the human's turn again.
    if (mode === "engine" && game.history().length > 0 && game.turn() !== humanColorRef.current) {
      game.undo();
    }
    sync();
    setError(null);
  }

  function reset() {
    if (thinking) return;
    gameRef.current = new Chess(fen);
    humanColorRef.current = gameRef.current.turn();
    sync();
    setError(null);
  }

  function toggleMode() {
    if (thinking) return;
    setMode((m) => (m === "free" ? "engine" : "free"));
    // The human keeps playing whoever is on the move right now.
    humanColorRef.current = game.turn();
  }

  const draggable = !thinking && !game.isGameOver() && (mode === "free" || game.turn() === humanColorRef.current);

  const status = game.isCheckmate()
    ? "Checkmate"
    : game.isStalemate()
      ? "Stalemate"
      : game.isDraw()
        ? "Draw"
        : thinking
          ? "Engine thinking…"
          : `${game.turn() === "w" ? "White" : "Black"} to move`;

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-app-border px-5 py-4">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-app-accent/80">{title}</p>
          <p className="mt-1 font-mono text-sm text-app-text">{status}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant={mode === "engine" ? "primary" : "secondary"} size="sm" onClick={toggleMode}>
            <Swords className="h-4 w-4" />
            {mode === "engine" ? "vs Engine: on" : "vs Engine: off"}
          </Button>
          {mode === "engine" && (
            <select
              value={skillLevel}
              onChange={(e) => setSkillLevel(Number(e.target.value))}
              disabled={thinking}
              aria-label="Engine difficulty"
              className="h-9 rounded-lg border border-app-border bg-app-panelSecondary px-3 text-sm text-app-text outline-none transition focus:border-app-accent/50 focus:ring-2 focus:ring-app-accent/40 disabled:text-app-faint"
            >
              {SKILL_LEVELS.map((lvl) => (
                <option key={lvl.value} value={lvl.value}>
                  {lvl.label}
                </option>
              ))}
            </select>
          )}
          <Button variant="ghost" size="sm" onClick={() => setBoardOrientation((o) => (o === "white" ? "black" : "white"))}>
            <FlipVertical2 className="h-4 w-4" />
            Flip
          </Button>
          <Button variant="ghost" size="sm" onClick={onExit}>
            <ChevronLeft className="h-4 w-4" />
            Back
          </Button>
        </div>
      </div>

      <div className="px-4 pb-5 sm:px-5">
        <div className="mx-auto max-w-[560px] overflow-hidden rounded-lg border border-app-border">
          <Chessboard
            id="explore-board"
            position={position}
            boardOrientation={boardOrientation}
            animationDuration={200}
            arePiecesDraggable={draggable}
            onPieceDrop={onPieceDrop}
            onPromotionPieceSelect={onPromotionPieceSelect}
            customDarkSquareStyle={{ backgroundColor: "#b58863" }}
            customLightSquareStyle={{ backgroundColor: "#f0d9b5" }}
            customBoardStyle={{ overflow: "hidden" }}
          />
        </div>

        {error && <p className="mt-3 text-sm text-app-blunder">{error}</p>}

        {history.length > 0 && (
          <p className="mt-3 break-words rounded-lg border border-app-border bg-app-panelSecondary/50 px-3 py-2 font-mono text-xs text-app-muted">
            {history
              .map((san, i) => (i % 2 === 0 ? `${Math.floor(i / 2) + 1}. ${san}` : san))
              .join(" ")}
          </p>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button variant="control" size="sm" onClick={takeBack} disabled={thinking || history.length === 0}>
            <Undo2 className="h-4 w-4" />
            Take back
          </Button>
          <Button variant="control" size="sm" onClick={reset} disabled={thinking || history.length === 0}>
            <RotateCcw className="h-4 w-4" />
            Reset
          </Button>
          <span className="text-xs text-app-muted">
            {mode === "engine" ? "You play the side to move; Stockfish replies." : "Move either side freely."}
          </span>
        </div>
      </div>
    </Card>
  );
}
