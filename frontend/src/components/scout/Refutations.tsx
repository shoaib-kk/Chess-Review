import { ArrowUpRight, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import type { ScoutRefutation } from "../../types";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { MiniBoard, eyebrowCls, evalText, frameSquares, pct, useFrames } from "./shared";
import type { OpenLine } from "./shared";

const SEVERITY_TONE = { inaccuracy: "yellow", mistake: "orange", blunder: "red" } as const;

function RefutationBoard({ item, id }: { item: ScoutRefutation; id: string }) {
  const steps = [
    { san: item.their_move, label: `They play ${item.their_move}` },
    ...item.punish_line.map((san, i) => ({ san, label: i === 0 ? `You reply ${san}` : san })),
  ];
  const frames = useFrames(item.fen, steps);
  const [index, setIndex] = useState(Math.min(2, frames.length - 1));
  useEffect(() => setIndex(Math.min(2, frames.length - 1)), [frames]);
  const frame = frames[index] ?? frames[0];
  // View from your side: you are the opposite colour to the opponent.
  const orientation = item.opponent_color === "white" ? "black" : "white";
  return (
    <div className="w-full max-w-[300px]">
      <MiniBoard id={id} fen={frame.fen} orientation={orientation} squares={frameSquares(frame)} />
      <div className="mt-2 flex items-center justify-between gap-2">
        <Button
          variant="control"
          size="sm"
          onClick={() => setIndex((i) => Math.max(0, i - 1))}
          disabled={index === 0}
          aria-label="Previous move"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="min-w-0 truncate text-center font-mono text-xs text-app-muted" aria-live="polite">
          {index === 0 ? "Before their move" : frame.label}
        </span>
        <Button
          variant="control"
          size="sm"
          onClick={() => setIndex((i) => Math.min(frames.length - 1, i + 1))}
          disabled={index >= frames.length - 1}
          aria-label="Next move"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function RefutationCard({ item, index, onOpen }: { item: ScoutRefutation; index: number; onOpen: OpenLine }) {
  return (
    <li className="rounded-xl border border-app-border bg-app-raised/40 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="break-words font-mono text-[13px] font-medium text-app-text">{item.line}</span>
        <Badge tone={SEVERITY_TONE[item.severity]}>{item.severity}</Badge>
        <Badge tone="neutral">{`They're ${item.opponent_color === "white" ? "White" : "Black"}`}</Badge>
      </div>
      <div className="mt-3 grid gap-4 sm:grid-cols-[minmax(0,300px)_1fr]">
        <RefutationBoard item={item} id={`scout-refutation-${index}`} />
        <div className="grid min-w-0 content-start gap-3 text-sm">
          <p className="text-app-muted">
            They play <span className="font-mono font-semibold text-app-text">{item.their_move}</span> in{" "}
            <span className="nums font-semibold text-app-text">{pct(item.their_share)}</span> of games here (
            {item.their_move_games} of {item.node_games}), scoring {pct(item.their_score_pct)}.
          </p>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg bg-app-panelSecondary px-2 py-2">
              <div className="nums text-sm font-semibold text-app-blunder">-{(item.loss_cp / 100).toFixed(1)}</div>
              <div className="mt-0.5 text-[10px] uppercase tracking-wider text-app-faint">Eval swing</div>
            </div>
            <div className="rounded-lg bg-app-panelSecondary px-2 py-2">
              <div className="nums text-sm font-semibold text-app-text">{evalText(item.eval_best_cp)}</div>
              <div className="mt-0.5 text-[10px] uppercase tracking-wider text-app-faint">With best</div>
            </div>
            <div className="rounded-lg bg-app-panelSecondary px-2 py-2">
              <div className="nums text-sm font-semibold text-app-text">{evalText(item.eval_after_cp)}</div>
              <div className="mt-0.5 text-[10px] uppercase tracking-wider text-app-faint">After habit</div>
            </div>
          </div>
          <p className="text-app-muted">
            They should play <span className="font-mono font-semibold text-app-text">{item.best_move}</span> instead.
          </p>
          <div className="rounded-lg border border-app-accentLine bg-app-accentSoft px-3 py-2">
            <p className={eyebrowCls}>Your punishing move</p>
            <p className="mt-1 font-mono text-sm font-semibold text-app-text">{item.punish_move}</p>
            <p className="mt-0.5 break-words font-mono text-xs text-app-muted">{item.punish_line.join(" ")}</p>
          </div>
          <div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onOpen(item.opponent_color, item.path)}
              aria-label={`Open ${item.line} in the explorer`}
            >
              <ArrowUpRight className="h-4 w-4" />
              Open in explorer
            </Button>
          </div>
        </div>
      </div>
    </li>
  );
}

export function Refutations({ items, onOpen }: { items: ScoutRefutation[]; onOpen: OpenLine }) {
  return (
    <section aria-labelledby="deep-refutations">
      <h3 id="deep-refutations" className="text-sm font-semibold text-app-text">
        Punish their habits
      </h3>
      <p className="mb-3 text-xs text-app-muted">
        Positions where their usual move is an engine-confirmed mistake, with your best reply.
      </p>
      {items.length ? (
        <ul className="grid gap-3">
          {items.map((item, i) => (
            <RefutationCard key={`${item.opponent_color}-${item.line}-${item.their_move}`} item={item} index={i} onOpen={onOpen} />
          ))}
        </ul>
      ) : (
        <p className="rounded-lg border border-dashed border-app-border px-4 py-6 text-center text-sm text-app-faint">
          No habitual move was found to be a clear engine mistake. Their opening choices hold up.
        </p>
      )}
    </section>
  );
}
