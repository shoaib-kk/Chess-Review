import type { GameSummary, MoveAnalysis, MoveClassification } from "../types";
import { Card } from "./ui/Card";

interface MoveListPanelProps {
  summary: GameSummary;
  currentIndex: number;
  onSelectMove: (index: number) => void;
  reviewMyMovesOnly?: boolean;
  embedded?: boolean;
}

const BADGES: Record<MoveClassification, string> = {
  Excellent: "",
  Inaccuracy: "?!",
  Mistake: "?",
  Blunder: "??",
};

const rowClasses: Record<MoveClassification, string> = {
  Excellent: "text-app-text hover:bg-app-panelSecondary/60",
  Inaccuracy: "text-app-warning hover:bg-app-warning/10",
  Mistake: "text-app-mistake hover:bg-app-mistake/10",
  Blunder: "text-app-blunder hover:bg-app-blunder/10",
};

const badgeStyles: Record<MoveClassification, { backgroundColor: string; color: string }> = {
  Excellent: { backgroundColor: "transparent", color: "inherit" },
  Inaccuracy: { backgroundColor: "#fbbf24", color: "#1e1e1e" },
  Mistake: { backgroundColor: "#fb923c", color: "#1e1e1e" },
  Blunder: { backgroundColor: "#f43f5e", color: "#ffffff" },
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
  if (!move || index === undefined) return <div className="min-h-9" />;

  return (
    <button
      className={`flex min-h-9 items-center justify-start gap-1.5 rounded-lg px-3 text-left font-mono text-sm transition ${
        active
          ? "bg-app-accentSoft text-app-text ring-1 ring-inset ring-app-accent/30"
          : rowClasses[move.classification]
      }`}
      onClick={onClick}
    >
      <span className="truncate">{move.move_played}</span>
      {BADGES[move.classification] && (
        <span
          className="inline-grid h-5 w-5 shrink-0 place-items-center rounded-full font-mono text-[9px] font-medium leading-none opacity-100"
          style={badgeStyles[move.classification]}
          aria-label={move.classification}
        >
          {BADGES[move.classification]}
        </span>
      )}
    </button>
  );
}

export function MoveListPanel({ summary, currentIndex, onSelectMove, reviewMyMovesOnly = false, embedded = false }: MoveListPanelProps) {
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

  const content = (
    <>
      <div className="px-5 pb-2 pt-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-app-accent/80">Notation</p>
        <h2 className="mt-1 text-base font-semibold text-app-text">{userColor ? `${userColor} moves` : "Move list"}</h2>
      </div>
      <div className="px-5 pb-4">
        <div className="mb-3 grid grid-cols-[42px_1fr_1fr] gap-2 border-b border-app-border px-1 pb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-app-muted">
          <div />
          <div>White</div>
          <div>Black</div>
        </div>
        <div className="max-h-[280px] space-y-1 overflow-y-auto pr-1">
          {pairs.map((pair) => (
            <div key={pair.moveNumber} className="grid grid-cols-[42px_1fr_1fr] items-center gap-2">
              <div className="pr-1 text-right font-mono text-sm text-app-muted">{pair.moveNumber}.</div>
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
      </div>
    </>
  );

  if (embedded) return <section>{content}</section>;

  return (
    <Card className="overflow-hidden">
      {content}
    </Card>
  );
}
