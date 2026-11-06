import { ArrowUpRight } from "lucide-react";
import type { ScoutTrappyLine } from "../../types";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { pct } from "./shared";
import type { OpenLine } from "./shared";

export function LichessTraps({
  traps,
  error,
  onOpen,
}: {
  traps: ScoutTrappyLine[] | null;
  error: string | null;
  onOpen: OpenLine;
}) {
  return (
    <section aria-labelledby="deep-traps">
      <h3 id="deep-traps" className="text-sm font-semibold text-app-text">
        Traps at their rating
      </h3>
      <p className="mb-3 text-xs text-app-muted">
        Replies that players at their level often choose but that score badly, checked against the Lichess database.
      </p>
      {traps === null ? (
        <p className="rounded-lg border border-dashed border-app-border px-4 py-5 text-sm text-app-faint">
          The Lichess database check was not available this time
          {error ? ` (${error})` : ""}. The other results above are unaffected; run the analysis again later to retry.
        </p>
      ) : traps.length ? (
        <ul className="grid gap-3">
          {traps.map((t) => {
            const played = t.their_moves_here.find((m) => m.san === t.trap_move);
            return (
              <li key={`${t.opponent_color}-${t.line}-${t.trap_move}`} className="rounded-xl border border-app-border bg-app-raised/40 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="break-words font-mono text-[13px] font-medium text-app-text">{t.line}</span>
                  <Badge tone="neutral">{`Rating ${t.rating_band}`}</Badge>
                  <Badge tone="neutral">{`They're ${t.opponent_color === "white" ? "White" : "Black"}`}</Badge>
                </div>
                <p className="mt-2 text-sm text-app-muted">
                  <span className="font-mono font-semibold text-app-text">{t.trap_move}</span> is chosen in{" "}
                  <span className="nums font-semibold text-app-text">{pct(t.trap_share)}</span> of {t.lichess_games.toLocaleString()} games but scores only{" "}
                  <span className="nums font-semibold text-app-good">{pct(t.trap_score_pct)}</span>
                  {t.best_move && t.best_score_pct !== null && (
                    <>
                      , against <span className="font-mono font-semibold text-app-text">{t.best_move}</span> at{" "}
                      <span className="nums font-semibold text-app-text">{pct(t.best_score_pct)}</span>
                    </>
                  )}
                  .
                </p>
                <p className="mt-1 text-xs text-app-faint">{t.reason}</p>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs text-app-muted">
                    {t.their_games_here > 0 ? (
                      <>
                        <Badge tone={played ? "yellow" : "neutral"}>{played ? "They have played it" : "Not played by them yet"}</Badge>{" "}
                        <span className="nums">
                          {t.their_games_here} of their games reach this position
                          {t.their_moves_here.length > 0 &&
                            ": " + t.their_moves_here.map((m) => `${m.san} x${m.games}`).join(", ")}
                        </span>
                      </>
                    ) : (
                      "None of their games reach this position."
                    )}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onOpen(t.opponent_color, t.path)}
                    aria-label={`Open ${t.line} in the explorer`}
                  >
                    <ArrowUpRight className="h-4 w-4" />
                    Open in explorer
                  </Button>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="rounded-lg border border-dashed border-app-border px-4 py-6 text-center text-sm text-app-faint">
          No clear traps found along their usual lines.
        </p>
      )}
    </section>
  );
}
