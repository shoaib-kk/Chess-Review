import { Chess } from "chess.js";
import { useEffect, useState } from "react";
import type { GameSummary, MoveAnalysis, MoveClassification } from "../types";
import { classificationMeta } from "../utils/classification";
import { formatEval, isMateScore, mateInMoves } from "../utils/evalFormat";
import { ClassificationBadge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";

interface AnalysisPanelProps {
  summary: GameSummary;
  currentIndex: number;
  embedded?: boolean;
}

const PIECE_VALUE: Record<string, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 };
const PIECE_NAME: Record<string, string> = {
  p: "pawn",
  n: "knight",
  b: "bishop",
  r: "rook",
  q: "queen",
  k: "king",
};

function coachHeadline(classification: MoveClassification): string {
  switch (classification) {
    case "Brilliant":
      return "Brilliant — a bold move that works.";
    case "Best":
      return "Best move — exactly what the engine plays.";
    case "Excellent":
      return "Excellent — essentially as good as the top move.";
    case "Good":
      return "A solid move with only a small concession.";
    case "Book":
      return "A known opening move — still in theory.";
    case "Inaccuracy":
      return "Playable, but the position offered a cleaner route.";
    case "Mistake":
      return "This noticeably changed the evaluation.";
    case "Miss":
      return "You missed a much stronger continuation here.";
    case "Blunder":
      return "Critical swing — this loses significant ground.";
    default:
      return "";
  }
}

/**
 * One-ply "is something hanging?" check on the position after the played move.
 * Finds the opponent capture that wins the most material (a free piece, or a
 * favourable exchange the player can't recapture). Conservative: only reports
 * captures that net at least a minor piece, to avoid crying wolf.
 */
function findHangingCapture(fenAfter: string): { square: string; piece: string; net: number } | null {
  let game: Chess;
  try {
    game = new Chess(fenAfter);
  } catch {
    return null;
  }

  let best: { square: string; piece: string; net: number } | null = null;
  for (const mv of game.moves({ verbose: true })) {
    if (!mv.captured) continue;
    const capturedVal = PIECE_VALUE[mv.captured] ?? 0;
    const attackerVal = PIECE_VALUE[mv.piece] ?? 0;
    game.move(mv);
    const canRecapture = game.moves({ verbose: true }).some((m) => m.to === mv.to && Boolean(m.captured));
    game.undo();
    const net = canRecapture ? capturedVal - attackerVal : capturedVal;
    if (net >= 2 && (!best || net > best.net)) {
      best = { square: mv.to, piece: mv.captured, net };
    }
  }
  return best;
}

/** A concrete reason an error move was bad, or null to fall back to generic copy. */
function explainMove(move: MoveAnalysis): string | null {
  if (!classificationMeta(move.classification).isError) return null;

  const beforeMover = move.eval_before; // already mover POV
  const afterMover = move.eval_after === null ? null : -move.eval_after; // flip to mover POV

  if (beforeMover !== null && isMateScore(beforeMover) && beforeMover > 0) {
    return move.best_move
      ? `You had a forced mate (M${mateInMoves(beforeMover)}); ${move.best_move} kept it going.`
      : `You had a forced mate available and let it slip.`;
  }

  if (afterMover !== null && isMateScore(afterMover) && afterMover < 0) {
    return `This allows a forced mate against you (M${mateInMoves(afterMover)}).`;
  }

  const hang = findHangingCapture(move.fen_after);
  if (hang) {
    const name = PIECE_NAME[hang.piece] ?? "piece";
    return move.best_move
      ? `This leaves your ${name} on ${hang.square} hanging; ${move.best_move} was safer.`
      : `This leaves your ${name} on ${hang.square} hanging.`;
  }

  return null;
}

export function AnalysisPanel({ summary, currentIndex, embedded = false }: AnalysisPanelProps) {
  const [showBestLine, setShowBestLine] = useState(false);
  const move = currentIndex >= 0 ? summary.move_analyses[currentIndex] : undefined;

  useEffect(() => {
    setShowBestLine(false);
  }, [currentIndex]);

  const meta = move ? classificationMeta(move.classification) : null;
  const reason = move ? explainMove(move) : null;
  const beforeMover = move?.eval_before ?? null;
  const afterMover = move?.eval_after === null || move?.eval_after === undefined ? null : -move.eval_after;

  const content = (
    <>
      <div className="pb-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">Selected move</p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-app-text">Coach panel</h2>
      </div>

      <div>
        {!move || !meta ? (
          <p className="text-sm leading-6 text-app-muted">
            Select a move from the graph, board controls, or move list to see the engine review.
          </p>
        ) : (
          <div className="border-l-2 pl-4" style={{ borderColor: meta.color }}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-app-faint">Move played</p>
                <div className="mt-1 font-mono text-2xl font-semibold text-app-text">
                  {move.move_number}
                  {move.color === "White" ? "." : "..."} {move.move_played}
                </div>
              </div>
              <ClassificationBadge classification={move.classification} />
            </div>

            <p className="mt-4 max-w-2xl text-sm leading-6 text-app-text">{coachHeadline(move.classification)}</p>
            {reason && (
              <p className="mt-2 max-w-2xl text-sm leading-6 text-app-muted">
                {reason}
              </p>
            )}

            <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
              <EvalStat
                label="Eval (your side)"
                value={`${formatEval(beforeMover)} → ${formatEval(afterMover)}`}
              />
              <EvalStat
                label="Move accuracy"
                value={move.move_accuracy !== null ? `${move.move_accuracy}%` : "-"}
              />
              <EvalStat
                label="Eval lost"
                value={move.cp_loss !== null ? `${(move.cp_loss / 100).toFixed(2)} pawns` : "-"}
              />
            </div>

            <div className="mt-5">
              <Button variant="secondary" size="sm" onClick={() => setShowBestLine((value) => !value)}>
                {showBestLine ? "Hide best line" : "Show best line"}
              </Button>
            </div>

            {showBestLine && <BestLine move={move} />}
          </div>
        )}

        {summary.user_username && (
          <div className="mt-6 grid gap-4 border-t border-app-border pt-5 text-sm sm:grid-cols-4">
            <UserStat label="My inaccuracies" value={summary.user_inaccuracies} />
            <UserStat label="My mistakes" value={summary.user_mistakes} />
            <UserStat label="My blunders" value={summary.user_blunders} />
            <UserStat label="My result" value={summary.user_result ?? "-"} />
          </div>
        )}
      </div>
    </>
  );

  if (embedded) return <section>{content}</section>;

  return <Card className="overflow-hidden">{content}</Card>;
}

function EvalStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-app-faint">{label}</div>
      <div className="mt-1 font-mono text-sm font-semibold text-app-text">{value}</div>
    </div>
  );
}

function BestLine({ move }: { move: MoveAnalysis }) {
  const line = move.pv.length ? move.pv : move.best_move ? [move.best_move] : [];
  const bestMove = move.best_move ?? line[0] ?? "-";
  const followUp = line[0] === bestMove ? line.slice(1) : line;

  return (
    <div className="mt-5 border-t border-app-border pt-4">
      <div className="grid gap-4 sm:grid-cols-[160px_1fr]">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">Best move</p>
          <p className="mt-1 font-mono text-lg font-semibold text-app-good">{bestMove}</p>
        </div>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">Follow-up line</p>
          <p className="mt-1 min-h-7 font-mono text-sm leading-6 text-app-text">
            {followUp.length ? followUp.join(" ") : "No follow-up returned"}
          </p>
        </div>
      </div>
    </div>
  );
}

function UserStat({ label, value }: { label: string; value: number | string | null }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-app-faint">{label}</div>
      <div className="mt-1 font-mono text-lg font-semibold text-app-text">{value ?? "-"}</div>
    </div>
  );
}
