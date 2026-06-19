// Stockfish reports a forced mate as (100000 - movesToMate) centipawns, so a
// mate score is always a very large value just under 100000.
export const MATE_CP_THRESHOLD = 90000;

export function isMateScore(cp: number): boolean {
  return Math.abs(cp) >= MATE_CP_THRESHOLD;
}

export function mateInMoves(cp: number): number {
  return Math.max(1, 100000 - Math.abs(cp));
}

/** Format a centipawn score (already in the desired POV) for display. */
export function formatEval(cp: number | null): string {
  if (cp === null) return "0.00";
  if (isMateScore(cp)) return `${cp > 0 ? "" : "-"}M${mateInMoves(cp)}`;
  const pawns = cp / 100;
  return `${pawns > 0 ? "+" : ""}${pawns.toFixed(2)}`;
}
