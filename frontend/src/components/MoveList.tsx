import type { GameSummary, MoveAnalysis } from "../types";
import { classificationMeta } from "../utils/classification";
import { Card } from "./ui/Card";

interface MoveListPanelProps {
  summary: GameSummary;
  currentIndex: number;
  onSelectMove: (index: number) => void;
  reviewMyMovesOnly?: boolean;
  embedded?: boolean;
}

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

  const meta = classificationMeta(move.classification);

  return (
    <button
      className={`flex min-h-9 items-center justify-start gap-1.5 rounded-lg px-3 text-left font-mono text-sm transition ${
        active
          ? "bg-app-accentSoft text-app-text ring-1 ring-inset ring-app-accent/30"
          : `${meta.textClass} hover:bg-app-panelSecondary/60`
      }`}
      onClick={onClick}
    >
      <span className="truncate">{move.move_played}</span>
      {meta.badgeSymbol && (
        <span
          className="inline-grid h-5 w-5 shrink-0 place-items-center rounded-full font-mono text-[9px] font-medium leading-none opacity-100"
          style={meta.annotation.backgroundColor === "transparent" ? { color: meta.color } : meta.annotation}
          aria-label={move.classification}
        >
          {meta.badgeSymbol}
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
      <div className="pb-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">Notation</p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-app-text">{userColor ? `${userColor} moves` : "Move list"}</h2>
      </div>
      <div>
        <div className="mb-3 grid grid-cols-[42px_1fr_1fr] gap-2 px-1 pb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-app-muted">
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
