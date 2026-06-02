import type { GameSummary, MoveAnalysis, MoveClassification } from "../types";
import { Badge } from "./ui/Badge";
import { Card, CardHeader } from "./ui/Card";

interface MoveListPanelProps {
  summary: GameSummary;
  currentIndex: number;
  onSelectMove: (index: number) => void;
  reviewMyMovesOnly?: boolean;
}

const BADGES: Record<MoveClassification, string> = {
  Excellent: "",
  Inaccuracy: "?!",
  Mistake: "?",
  Blunder: "??",
};

const rowClasses: Record<MoveClassification, string> = {
  Excellent: "hover:bg-app-panelSecondary/70",
  Inaccuracy: "bg-app-warning/10 text-yellow-100 hover:bg-app-warning/15",
  Mistake: "bg-app-mistake/10 text-orange-100 hover:bg-app-mistake/15",
  Blunder: "bg-app-blunder/12 text-red-100 hover:bg-app-blunder/18",
};

const badgeTone: Record<MoveClassification, "neutral" | "green" | "yellow" | "orange" | "red"> = {
  Excellent: "neutral",
  Inaccuracy: "yellow",
  Mistake: "orange",
  Blunder: "red",
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
      className={`flex min-h-9 items-center justify-between gap-2 rounded-md px-3 text-left font-mono text-sm transition ${
        active
          ? "bg-app-accent text-white shadow-glow"
          : `text-slate-200 ${rowClasses[move.classification]}`
      }`}
      onClick={onClick}
    >
      <span className="truncate">{move.move_played}</span>
      {BADGES[move.classification] && (
        <Badge tone={badgeTone[move.classification]} className="shrink-0 px-1.5 py-0 text-[10px]">
          {BADGES[move.classification]}
        </Badge>
      )}
    </button>
  );
}

export function MoveListPanel({ summary, currentIndex, onSelectMove, reviewMyMovesOnly = false }: MoveListPanelProps) {
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
    <Card className="overflow-hidden">
      <CardHeader title={userColor ? `${userColor} moves` : "Move list"} eyebrow="Notation">
        Click any move to jump through the review.
      </CardHeader>

      <div className="px-5 pb-5">
        <div className="mb-2 grid grid-cols-[42px_1fr_1fr] gap-2 px-1 text-[11px] font-bold uppercase tracking-[0.12em] text-app-muted">
          <div />
          <div>White</div>
          <div>Black</div>
        </div>
        <div className="max-h-[300px] space-y-1.5 overflow-y-auto pr-1">
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
    </Card>
  );
}
