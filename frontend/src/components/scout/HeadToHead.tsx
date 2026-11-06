import { ArrowUpRight } from "lucide-react";
import type { ScoutingReport } from "../../types";
import { Badge } from "../ui/Badge";
import { Card, CardHeader } from "../ui/Card";
import { StatCard } from "../ui/StatCard";
import { WinLossBar } from "../ui/WinLossBar";
import { InsightList, SplitRow, eyebrowCls, pct } from "./shared";
import type { OpenLine } from "./shared";

export function HeadToHead({ report, onOpen }: { report: ScoutingReport; onOpen: OpenLine }) {
  const h = report.head_to_head;
  if (!h) return null;
  return (
    <Card>
      <CardHeader title={`${h.me} vs ${report.username}`} eyebrow="Head to head">
        Your past games against each other, from your point of view.
      </CardHeader>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-app-border bg-app-raised/50 p-4 sm:col-span-1">
          <p className={eyebrowCls}>Your record</p>
          <p className="nums mt-1 text-2xl font-semibold text-app-text">
            {h.wins}-{h.draws}-{h.losses}
          </p>
          <p className="nums text-xs text-app-muted">
            {h.games} games · you score {pct(h.score_pct)}
          </p>
          <WinLossBar wins={h.wins} draws={h.draws} losses={h.losses} className="mt-2" />
        </div>
        <StatCard
          label="Your accuracy"
          value={h.your_avg_accuracy !== null ? h.your_avg_accuracy.toFixed(0) : "–"}
          caption="in these games"
        />
        <StatCard
          label="Their accuracy"
          value={h.their_avg_accuracy !== null ? h.their_avg_accuracy.toFixed(0) : "–"}
          caption="in these games"
        />
      </div>

      {h.insights.length > 0 && <InsightList items={h.insights} className="mt-4" />}

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <div>
          <p className={`${eyebrowCls} mb-3`}>By colour</p>
          <div className="grid gap-3">
            <SplitRow split={h.you_white} />
            <SplitRow split={h.you_black} />
          </div>

          <p className={`${eyebrowCls} mb-2 mt-5`}>Lines you keep reaching</p>
          {h.repeated_lines.length ? (
            <ul className="grid gap-2">
              {h.repeated_lines.map((row) => (
                <li key={`${row.you_color}-${row.line}`}>
                  <button
                    type="button"
                    onClick={() => onOpen(row.you_color === "white" ? "black" : "white", row.path)}
                    aria-label={`Open ${row.line} in the explorer`}
                    className="group w-full rounded-lg border border-app-border bg-app-raised/50 px-3 py-2.5 text-left transition hover:border-app-borderStrong hover:bg-app-raised"
                  >
                    <span className="flex items-start justify-between gap-2">
                      <span className="break-words font-mono text-[13px] font-medium text-app-text">{row.line}</span>
                      <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-app-faint group-hover:text-app-accent" />
                    </span>
                    <span className="nums mt-1 block text-xs text-app-muted">
                      You: {row.you_color === "white" ? "White" : "Black"} · {row.games} games · you score{" "}
                      {pct(row.your_score_pct)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-app-faint">No opening repeated often enough yet.</p>
          )}
        </div>

        <div>
          <p className={`${eyebrowCls} mb-2`}>Recent games</p>
          {h.recent.length ? (
            <ul className="grid gap-1.5">
              {h.recent.map((g, i) => (
                <li
                  key={`${g.url ?? "x"}-${i}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-app-panelSecondary px-3 py-2 text-xs"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <Badge tone={g.result === "win" ? "green" : g.result === "loss" ? "red" : "neutral"}>
                      {g.result === "win" ? "Won" : g.result === "loss" ? "Lost" : "Drew"}
                    </Badge>
                    <span className="truncate text-app-muted">
                      as {g.you_color} · {g.opening || "Unknown opening"}
                      {g.time_class ? ` · ${g.time_class}` : ""}
                    </span>
                  </span>
                  {g.url ? (
                    <a
                      href={g.url}
                      target="_blank"
                      rel="noreferrer"
                      aria-label={`Open game from ${g.date ?? "unknown date"}`}
                      className="shrink-0 text-app-faint hover:text-app-accent"
                    >
                      {g.date ?? "view"}
                    </a>
                  ) : (
                    <span className="shrink-0 text-app-faint">{g.date ?? ""}</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-app-faint">No recent games listed.</p>
          )}
        </div>
      </div>
    </Card>
  );
}
