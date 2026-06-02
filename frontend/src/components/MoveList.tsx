import type { GameSummary, MoveAnalysis, MoveClassification } from "../types";

interface MoveListProps {
  summary: GameSummary;
  currentIndex: number;
  onSelectMove: (index: number) => void;
  reviewMyMovesOnly?: boolean;
}

const BADGES: Record<MoveClassification, string> = {
  Excellent: "✓",
  Inaccuracy: "?!",
  Mistake: "?",
  Blunder: "??",
};

const COLORS: Record<MoveClassification, string> = {
  Excellent: "bg-emerald-400 text-slate-950",
  Inaccuracy: "bg-yellow-300 text-slate-950",
  Mistake: "bg-orange-400 text-slate-950",
  Blunder: "bg-red-500 text-white",
};

function MoveButton({
  move,
  index,
  active,
  onClick,
}: {
  move?: MoveAnalysis;
  index?: number;
  active: boolean;
  onClick: () => void;
}) {
  if (!move || index === undefined) return <div />;

  return (
    <button
      className={`flex min-h-9 items-center justify-between rounded px-3 text-left font-mono text-sm transition ${
        active ? "bg-app-accent text-white" : "bg-slate-950/70 text-slate-200 hover:bg-slate-900"
      }`}
      onClick={onClick}
    >
      <span>{move.move_played}</span>
      {move.classification !== "Excellent" && (
        <span className={`rounded px-1.5 py-0.5 text-[11px] font-black ${COLORS[move.classification]}`}>
          {BADGES[move.classification]}
        </span>
      )}
    </button>
  );
}

export function MoveList({ summary, currentIndex, onSelectMove, reviewMyMovesOnly = false }: MoveListProps) {
  const pairs: Array<{ moveNumber: number; white?: [MoveAnalysis, number]; black?: [MoveAnalysis, number] }> = [];
  const userColor = reviewMyMovesOnly ? summary.user_color : null;

  summary.move_analyses.forEach((move, index) => {
    if (userColor && move.color !== userColor) return;
    let pair = pairs.find((item) => item.moveNumber === move.move_number);
    if (!pair) {
      pair = { moveNumber: move.move_number };
      pairs.push(pair);
    }
    if (move.color === "White") pair.white = [move, index];
    else pair.black = [move, index];
  });

  return (
    <section className="rounded bg-app-panel p-4 shadow-panel">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
          {userColor ? `${userColor} Moves` : "Moves"}
        </p>
        {userColor && <span className="text-xs text-slate-500">filtered</span>}
      </div>
      <div className="max-h-[360px] space-y-2 overflow-y-auto pr-1">
        {pairs.map((pair) => (
          <div key={pair.moveNumber} className="grid grid-cols-[42px_1fr_1fr] items-center gap-2">
            <div className="text-right font-mono text-sm text-slate-500">{pair.moveNumber}.</div>
            <MoveButton
              move={pair.white?.[0]}
              index={pair.white?.[1]}
              active={pair.white?.[1] === currentIndex}
              onClick={() => pair.white && onSelectMove(pair.white[1])}
            />
            <MoveButton
              move={pair.black?.[0]}
              index={pair.black?.[1]}
              active={pair.black?.[1] === currentIndex}
              onClick={() => pair.black && onSelectMove(pair.black[1])}
            />
          </div>
        ))}
      </div>
    </section>
  );
}
