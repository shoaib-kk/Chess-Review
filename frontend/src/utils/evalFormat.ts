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

// Logistic centipawns -> win chance, matching the backend (accuracy.py /
// models.cp_to_win_chance) so the graph and the accuracy numbers agree.
const WIN_CHANCE_K = 0.00368208;
const MAX_CP_FOR_WIN_CHANCE = 4000;

/** Centipawns (POV of whoever you want the chance for) -> win chance 0-100. */
export function cpToWinChance(cp: number | null): number {
  if (cp === null) return 50;
  const bounded = Math.max(-MAX_CP_FOR_WIN_CHANCE, Math.min(MAX_CP_FOR_WIN_CHANCE, cp));
  const chance = 50 + 50 * (2 / (1 + Math.exp(-WIN_CHANCE_K * bounded)) - 1);
  return Math.max(0, Math.min(100, chance));
}
