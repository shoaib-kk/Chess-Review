import { Chess, type Square } from "chess.js";
import { useEffect, useState } from "react";
import type { AnalysisLine, GameSummary, MoveAnalysis, MoveClassification } from "../types";
import { classificationMeta } from "../utils/classification";
import { formatEval, isMateScore, mateInMoves } from "../utils/evalFormat";
import { ClassificationBadge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";

interface AnalysisPanelProps {
  summary: GameSummary;
  currentIndex: number;
  analysisLine?: AnalysisLine | null;
  onPlayLine?: (line: AnalysisLine | null) => void;
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
      return "Brilliant — a bold sacrifice that works.";
    case "Great":
      return "Great move — the critical move when everything else was much worse.";
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

/**
 * Detect a fork / double attack the played move walks into: an opponent move
 * after which one of their pieces hits two or more of your valuable pieces (or
 * your king plus a piece), winning material. Uses chess.js `attackers`; returns
 * null on engines/positions where nothing qualifies. Conservative — it only
 * fires when at least one target is higher-value than the attacker, undefended,
 * or the king, so it doesn't cry "fork" at every contact.
 */
function findFork(fenAfter: string): { forker: string; square: string; targets: string[] } | null {
  let game: Chess;
  try {
    game = new Chess(fenAfter);
  } catch {
    return null;
  }
  const attackersOf = (game as unknown as { attackers?: unknown }).attackers;
  if (typeof attackersOf !== "function") return null;

  const them = game.turn();
  const us = them === "w" ? "b" : "w";
  let best: { forker: string; square: string; targets: string[]; score: number } | null = null;

  for (const mv of game.moves({ verbose: true })) {
    game.move(mv);
    const forker = game.get(mv.to as Square);
    const forkerVal = forker ? PIECE_VALUE[forker.type] : 0;
    const targets: { name: string; val: number; defended: boolean }[] = [];

    for (const row of game.board()) {
      for (const cell of row) {
        if (!cell || cell.color !== us) continue;
        const isKing = cell.type === "k";
        const baseVal = PIECE_VALUE[cell.type] ?? 0;
        if (!isKing && baseVal < 3) continue;
        const atk = (game.attackers(cell.square, them) ?? []) as string[];
        if (!atk.includes(mv.to)) continue;
        const def = (game.attackers(cell.square, us) ?? []) as string[];
        targets.push({ name: PIECE_NAME[cell.type], val: isKing ? 100 : baseVal, defended: def.length > 0 });
      }
    }
    game.undo();

    if (targets.length < 2) continue;
    const winsMaterial = targets.some((t) => t.val === 100 || t.val > forkerVal || !t.defended);
    if (!winsMaterial) continue;

    const score = targets.reduce((sum, t) => sum + t.val, 0);
    if (!best || score > best.score) {
      best = { forker: PIECE_NAME[forker?.type ?? "p"], square: mv.to, targets: targets.map((t) => t.name), score };
    }
  }

  return best ? { forker: best.forker, square: best.square, targets: best.targets } : null;
}

function forkTargetPhrase(targets: string[]): string {
  const unique = Array.from(new Set(targets));
  if (unique.length === 1) return `two of your ${unique[0]}s`;
  if (unique.length === 2) return `your ${unique[0]} and ${unique[1]}`;
  return `your ${unique.slice(0, -1).join(", ")}, and ${unique[unique.length - 1]}`;
}

/** Plain-language read of where a position leaves the mover (mover-POV cp). */
function standing(cpMover: number | null): string {
  if (cpMover === null) return "";
  if (isMateScore(cpMover)) return cpMover > 0 ? " with a forced mate" : " and gets mated";
  if (cpMover <= -300) return ", leaving you losing";
  if (cpMover <= -100) return ", leaving you clearly worse";
  if (cpMover < -30) return ", giving your opponent the edge";
  if (cpMover <= 30) return ", letting the advantage slip to roughly equal";
  return "";
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

  const fork = findFork(move.fen_after);
  if (fork) {
    const base = `This allows a ${fork.forker} fork on ${fork.square}, hitting ${forkTargetPhrase(fork.targets)}`;
    return move.best_move ? `${base}; ${move.best_move} avoided it.` : `${base}.`;
  }

  // Concrete fallback: name the better move and quantify what was given up,
  // rather than the generic "this changed the evaluation".
  if (move.best_move && move.best_move !== move.move_played && move.cp_loss !== null) {
    const pawns = move.cp_loss / 100;
    if (pawns >= 0.3) {
      return `${move.best_move} was stronger — ${move.move_played} gives up about ${pawns.toFixed(1)} pawns${standing(afterMover)}.`;
    }
  }

  return null;
}

export function AnalysisPanel({ summary, currentIndex, analysisLine, onPlayLine, embedded = false }: AnalysisPanelProps) {
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

            <TopMoves move={move} analysisLine={analysisLine ?? null} onPlayLine={onPlayLine} />

            <div className="mt-5">
              <Button variant="secondary" size="sm" onClick={() => setShowBestLine((value) => !value)}>
                {showBestLine ? "Hide best line" : "Show best line"}
              </Button>
            </div>

            {showBestLine && <BestLine move={move} analysisLine={analysisLine ?? null} onPlayLine={onPlayLine} />}
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

/** Eval (mover POV centipawns) styled by who it favours. */
function CandidateEval({ cp }: { cp: number | null }) {
  const tone = cp === null ? "text-app-muted" : cp >= 30 ? "text-app-good" : cp <= -30 ? "text-app-blunder" : "text-app-muted";
  return <span className={`font-mono text-xs font-semibold ${tone}`}>{formatEval(cp)}</span>;
}

/** The engine's top candidate moves with evals — click one to see it on the board. */
function TopMoves({
  move,
  analysisLine,
  onPlayLine,
}: {
  move: MoveAnalysis;
  analysisLine: AnalysisLine | null;
  onPlayLine?: (line: AnalysisLine | null) => void;
}) {
  const candidates = move.top_moves ?? [];
  if (candidates.length === 0) return null;

  const activeFirst =
    analysisLine && analysisLine.baseFen === move.fen_before && analysisLine.moves.length >= 1
      ? analysisLine.moves[0]
      : null;

  return (
    <div className="mt-5 border-t border-app-border pt-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">Top engine moves</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {candidates.map((cand, i) => {
          const active = activeFirst === cand.move;
          return (
            <button
              key={`${cand.move}-${i}`}
              type="button"
              disabled={!onPlayLine}
              onClick={() => onPlayLine?.({ baseFen: move.fen_before, moves: [cand.move] })}
              className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 transition ${
                active ? "border-app-accent bg-app-accent/10" : "border-app-border bg-app-panelSecondary hover:border-app-accent/50"
              } ${onPlayLine ? "cursor-pointer" : "cursor-default"}`}
            >
              <span className="font-mono text-sm font-semibold text-app-text">{cand.move}</span>
              <CandidateEval cp={cand.eval} />
            </button>
          );
        })}
      </div>
      {onPlayLine && <p className="mt-1.5 text-[11px] text-app-faint">Click a move to play it on the board.</p>}
    </div>
  );
}

function BestLine({
  move,
  analysisLine,
  onPlayLine,
}: {
  move: MoveAnalysis;
  analysisLine: AnalysisLine | null;
  onPlayLine?: (line: AnalysisLine | null) => void;
}) {
  const line = move.pv.length ? move.pv : move.best_move ? [move.best_move] : [];
  const activeDepth =
    analysisLine && analysisLine.baseFen === move.fen_before ? analysisLine.moves.length : 0;

  if (line.length === 0) {
    return (
      <div className="mt-5 border-t border-app-border pt-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">Best line</p>
        <p className="mt-1 font-mono text-sm text-app-muted">No line returned</p>
      </div>
    );
  }

  return (
    <div className="mt-5 border-t border-app-border pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">Best line</p>
        {onPlayLine && (
          <button
            type="button"
            onClick={() => onPlayLine({ baseFen: move.fen_before, moves: line })}
            className="font-mono text-[11px] font-semibold text-app-accent hover:underline"
          >
            Play whole line →
          </button>
        )}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {line.map((san, i) => {
          const active = onPlayLine ? i < activeDepth : false;
          return (
            <button
              key={`${san}-${i}`}
              type="button"
              disabled={!onPlayLine}
              onClick={() => onPlayLine?.({ baseFen: move.fen_before, moves: line.slice(0, i + 1) })}
              className={`rounded-md px-1.5 py-0.5 font-mono text-sm transition ${
                active ? "bg-app-accent/20 text-app-text" : "text-app-text hover:bg-app-panelSecondary"
              } ${i === 0 ? "font-semibold text-app-good" : ""} ${onPlayLine ? "cursor-pointer" : "cursor-default"}`}
            >
              {san}
            </button>
          );
        })}
      </div>
      {onPlayLine && (
        <p className="mt-1.5 text-[11px] text-app-faint">Click any move to step the line out on the board.</p>
      )}
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
