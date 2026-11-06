import { useState } from "react";
import type { ReactNode } from "react";
import type { ScoutFingerprint, ScoutMistakeExample } from "../../types";
import { Badge } from "../ui/Badge";
import { InsightList, MiniBoard, eyebrowCls, pct, turnOf } from "./shared";

function Sub({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-w-0 rounded-xl border border-app-border bg-app-raised/40 p-4">
      <p className={`${eyebrowCls} mb-3`}>{title}</p>
      {children}
    </div>
  );
}

function Big({ label, value, caption }: { label: string; value: string; caption?: string }) {
  return (
    <div className="rounded-xl border border-app-border bg-app-raised/50 p-4">
      <p className={eyebrowCls}>{label}</p>
      <p className="nums mt-1 text-2xl font-semibold text-app-text">{value}</p>
      {caption && <p className="text-xs text-app-muted">{caption}</p>}
    </div>
  );
}

function ExampleBoard({ ex, id }: { ex: ScoutMistakeExample; id: string }) {
  return (
    <div className="w-full max-w-[260px]">
      <MiniBoard id={id} fen={ex.fen} orientation={turnOf(ex.fen)} />
      <p className="mt-2 text-xs text-app-muted">
        Move {ex.move_number}, {ex.color}: played <span className="font-mono font-semibold text-app-blunder">{ex.played}</span>, best was{" "}
        <span className="font-mono font-semibold text-app-good">{ex.best}</span> (-{(ex.cp_loss / 100).toFixed(1)}).
        {ex.url && (
          <>
            {" "}
            <a href={ex.url} target="_blank" rel="noreferrer" className="text-app-accent hover:underline">
              Game
            </a>
          </>
        )}
      </p>
    </div>
  );
}

function Cliff({ row }: { row: ScoutFingerprint["opening_cliffs"][number] }) {
  const max = Math.max(1, ...row.by_move.map((m) => m.avg_cp_loss));
  return (
    <li className="rounded-lg bg-app-panelSecondary px-3 py-2">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs">
        <span className="font-medium text-app-text">
          {row.family} <span className="text-app-faint">as {row.color} · {row.games}g</span>
        </span>
        <span className="text-app-muted">
          {row.cliff_move !== null ? (
            <>
              cliff at move <span className="nums font-semibold text-app-blunder">{row.cliff_move}</span>
              {row.avg_cp_loss_before !== null && row.avg_cp_loss_after !== null && (
                <span className="nums text-app-faint">
                  {" "}
                  ({row.avg_cp_loss_before.toFixed(0)} to {row.avg_cp_loss_after.toFixed(0)} cp)
                </span>
              )}
            </>
          ) : (
            "no clear cliff"
          )}
        </span>
      </div>
      <div className="mt-2 flex h-10 items-end gap-0.5" role="img" aria-label={`Average centipawn loss by move for ${row.family}`}>
        {row.by_move.map((m) => (
          <div
            key={m.move}
            title={`Move ${m.move}: ${m.avg_cp_loss.toFixed(0)} cp (${m.samples} samples)`}
            className={`min-w-[3px] flex-1 rounded-sm ${m.move === row.cliff_move ? "bg-app-blunder" : "bg-app-accent/60"}`}
            style={{ height: `${Math.max(6, (m.avg_cp_loss / max) * 100)}%` }}
          />
        ))}
      </div>
    </li>
  );
}

export function Fingerprint({ data }: { data: ScoutFingerprint | null }) {
  const [motifIndex, setMotifIndex] = useState<number | null>(null);
  if (!data) {
    return (
      <section>
        <h3 className="text-sm font-semibold text-app-text">How they go wrong</h3>
        <p className="mt-2 rounded-lg border border-dashed border-app-border px-4 py-5 text-sm text-app-faint">
          Not enough analysable games to build a mistake profile.
        </p>
      </section>
    );
  }
  const motifMax = Math.max(1, ...data.motifs.map((m) => m.pct));
  const selected = motifIndex !== null ? data.motifs[motifIndex] : undefined;
  return (
    <section aria-labelledby="deep-fingerprint" className="grid gap-4">
      <div>
        <h3 id="deep-fingerprint" className="text-sm font-semibold text-app-text">
          How they go wrong
        </h3>
        <p className="text-xs text-app-muted">
          Stockfish depth {data.depth} over {data.games_analyzed} games ({data.moves_analyzed} of their moves).
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Big label="Average error per move" value={data.avg_cp_loss !== null ? data.avg_cp_loss.toFixed(0) : "–"} caption="hundredths of a pawn; under 30 is clean, over 60 is loose" />
        <Big label="Accuracy" value={data.accuracy_estimate !== null ? `${data.accuracy_estimate.toFixed(0)}%` : "–"} caption="like Chess.com's game review score" />
        <Big
          label="Wins when ahead / saves when behind"
          value={`${pct(data.conversion.converted_pct)} / ${pct(data.conversion.saved_pct)}`}
          caption={`${data.conversion.converted} of ${data.conversion.winning_games} winning, ${data.conversion.saved} of ${data.conversion.losing_games} losing`}
        />
      </div>

      <InsightList items={data.insights} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Sub title="By phase">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[320px] text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-app-faint">
                  <th className="pb-2 font-medium">Phase</th>
                  <th className="pb-2 text-right font-medium">Avg error</th>
                  <th className="pb-2 text-right font-medium">Mistakes</th>
                  <th className="pb-2 text-right font-medium">Blunders</th>
                  <th className="pb-2 text-right font-medium" title="Blunders per 100 moves">Per 100</th>
                </tr>
              </thead>
              <tbody>
                {data.phases.map((p) => (
                  <tr key={p.phase} className="border-t border-app-border/60">
                    <td className="py-2 capitalize text-app-text">{p.phase}</td>
                    <td className="nums py-2 text-right text-app-muted">{p.avg_cp_loss !== null ? p.avg_cp_loss.toFixed(0) : "–"}</td>
                    <td className="nums py-2 text-right text-app-muted">{p.mistakes}</td>
                    <td className="nums py-2 text-right text-app-muted">{p.blunders}</td>
                    <td className="nums py-2 text-right font-semibold text-app-text">{p.blunder_rate.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Sub>

        <Sub title="Under time pressure">
          {data.time_pressure.buckets.length ? (
            <ul className="grid gap-2.5">
              {data.time_pressure.buckets.map((b) => (
                <li key={b.key}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="text-app-muted">{b.label}</span>
                    <span className="nums text-xs text-app-faint">
                      {b.moves} moves ·{" "}
                      <span className="font-semibold text-app-text">{b.avg_cp_loss !== null ? `${b.avg_cp_loss.toFixed(0)} cp` : "–"}</span> ·{" "}
                      {b.blunder_rate.toFixed(1)} blunders/100
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
                    <div
                      className="h-full rounded-full bg-app-warning/70"
                      style={{ width: `${Math.min(100, (b.blunder_rate / Math.max(1, ...data.time_pressure.buckets.map((x) => x.blunder_rate))) * 100)}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-app-faint">No clock data in these games.</p>
          )}
        </Sub>
      </div>

      <Sub title="Mistake types">
        {data.motifs.length ? (
          <div className="grid gap-4 md:grid-cols-[1fr_auto]">
            <ul className="grid gap-1.5">
              {data.motifs.map((m, i) => (
                <li key={m.motif}>
                  <button
                    type="button"
                    disabled={!m.example}
                    onClick={() => setMotifIndex(motifIndex === i ? null : i)}
                    aria-pressed={motifIndex === i}
                    aria-label={`${m.label}: ${m.count} mistakes${m.example ? ", show example" : ""}`}
                    className={`w-full rounded-lg px-2 py-1.5 text-left transition ${
                      motifIndex === i ? "bg-app-raisedHover" : "hover:bg-app-raised"
                    } disabled:cursor-default disabled:hover:bg-transparent`}
                  >
                    <div className="flex justify-between text-sm">
                      <span className="text-app-muted">{m.label}</span>
                      <span className="nums text-app-text">
                        {m.count} · {pct(m.pct)}
                      </span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
                      <div className="h-full rounded-full bg-app-blunder/70" style={{ width: `${(m.pct / motifMax) * 100}%` }} />
                    </div>
                  </button>
                </li>
              ))}
            </ul>
            <div className="md:min-w-[260px]">
              {selected?.example ? (
                <ExampleBoard ex={selected.example} id="scout-motif-example" />
              ) : (
                <p className="text-xs text-app-faint">Select a mistake type to see an example position.</p>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-app-faint">No classified mistakes.</p>
        )}
      </Sub>

      {data.opening_cliffs.length > 0 && (
        <Sub title="Opening cliffs">
          <p className="mb-2 text-xs text-app-muted">
            How big their errors are at each move number (taller = worse). The red bar is where their play drops off: they've left what they know.
          </p>
          <ul className="grid gap-2">
            {data.opening_cliffs.map((row) => (
              <Cliff key={`${row.color}-${row.family}`} row={row} />
            ))}
          </ul>
        </Sub>
      )}

      {data.worst_mistakes.length > 0 && (
        <Sub title="Worst mistakes">
          <ul className="grid gap-2">
            {data.worst_mistakes.map((ex, i) => (
              <li key={`${ex.fen}-${i}`} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-app-panelSecondary px-3 py-2 text-xs">
                <span className="min-w-0 text-app-muted">
                  Move {ex.move_number} as {ex.color} in {ex.family}: played{" "}
                  <span className="font-mono font-semibold text-app-blunder">{ex.played}</span>, best{" "}
                  <span className="font-mono font-semibold text-app-good">{ex.best}</span>
                </span>
                <span className="flex items-center gap-2">
                  <Badge tone="red">{`-${(ex.cp_loss / 100).toFixed(1)}`}</Badge>
                  {ex.clock_pct !== null && <span className="nums text-app-faint">{ex.clock_pct.toFixed(0)}% clock</span>}
                  {ex.url && (
                    <a href={ex.url} target="_blank" rel="noreferrer" className="text-app-accent hover:underline">
                      Game
                    </a>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Sub>
      )}
    </section>
  );
}
