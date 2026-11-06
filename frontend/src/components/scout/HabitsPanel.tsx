import { Clock } from "lucide-react";
import type { ReactNode } from "react";
import type { ScoutHabits, ScoutingReport } from "../../types";
import { Badge } from "../ui/Badge";
import { Card, CardHeader } from "../ui/Card";
import { Delta } from "../ui/Delta";
import { WinLossBar } from "../ui/WinLossBar";
import { InsightList, SplitRow, eyebrowCls, pct } from "./shared";

const REASON_LABEL: Record<string, string> = {
  resignation: "Resigned",
  checkmate: "Checkmated",
  time: "Lost on time",
  abandoned: "Abandoned",
  other: "Other",
  agreed: "Agreed",
  repetition: "Repetition",
  stalemate: "Stalemate",
  insufficient: "Insufficient material",
  "50move": "50-move rule",
  timevsinsufficient: "Time vs insufficient",
};

function Sub({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-w-0 rounded-xl border border-app-border bg-app-raised/40 p-4">
      <p className={`${eyebrowCls} mb-3`}>{title}</p>
      {children}
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg bg-app-panelSecondary px-3 py-2" title={hint}>
      <div className="nums text-sm font-semibold text-app-text">{value}</div>
      <div className="mt-0.5 text-[10px] uppercase tracking-wider text-app-faint">{label}</div>
    </div>
  );
}

function SessionsTilt({ h }: { h: ScoutHabits }) {
  const s = h.sessions;
  return (
    <Sub title="Sessions & tilt">
      <p className="mb-3 text-xs text-app-muted">
        {s.sessions} sessions (games within {s.session_gap_minutes} min of each other)
        {s.avg_games_per_session !== null && <>, averaging {s.avg_games_per_session.toFixed(1)} games each</>}.
      </p>
      <div className="grid gap-2.5">
        <SplitRow split={s.after_win} />
        <SplitRow split={s.after_draw} />
        <SplitRow split={s.after_loss} />
        <SplitRow split={s.on_losing_streak} />
      </div>
      <p className={`${eyebrowCls} mb-2 mt-4`}>By game number in a session</p>
      <div className="grid gap-2.5">
        {s.by_session_index.map((row) => (
          <SplitRow key={row.key} split={row} />
        ))}
      </div>
    </Sub>
  );
}

function TimeBlock({ h }: { h: ScoutHabits }) {
  return (
    <Sub title="When they play">
      <p className="mb-2 text-xs text-app-faint">
        <Clock className="mr-1 inline h-3 w-3" />
        Local time
      </p>
      <div className="grid gap-2.5">
        {h.time_of_day.map((row) => (
          <SplitRow key={row.key} split={row} />
        ))}
      </div>
      <p className={`${eyebrowCls} mb-2 mt-4`}>Weekday</p>
      <div className="grid gap-2.5">
        {h.weekday.map((row) => (
          <SplitRow key={row.key} split={row} />
        ))}
      </div>
    </Sub>
  );
}

function PositionComfort({ h }: { h: ScoutHabits }) {
  const rows = h.positions.filter((p) => p.games > 0);
  return (
    <Sub title="Position-type comfort">
      {rows.length ? (
        <div className="grid gap-3">
          {rows.map((p) => (
            <div key={p.key}>
              <SplitRow split={p} extra={p.description} />
              <p className="mt-0.5 text-[11px] text-app-faint">
                {pct(p.share)} of their games · {p.description}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-app-faint">Not enough games to classify positions.</p>
      )}
    </Sub>
  );
}

function ResignDraw({ h }: { h: ScoutHabits }) {
  const r = h.resignation;
  const d = h.draws;
  return (
    <Sub title="Resignation & draw habits">
      <div className="grid grid-cols-2 gap-2">
        <Stat label="Resigned while not behind" value={pct(r.resigned_not_behind_pct)} hint={`${r.resigned_not_behind} of ${r.resignations} resignations`} />
        <Stat label="Played on in lost positions" value={pct(r.played_on_lost_pct)} hint={`${r.played_on_lost} games`} />
        <Stat label="Comeback rate" value={pct(r.comeback_rate_pct)} hint={`${r.comebacks} games won or drawn from 3+ down`} />
        <Stat label="Collapse rate" value={pct(r.collapse_rate_pct)} hint={`${r.collapses_from_ahead} games lost from 3+ up`} />
      </div>
      {r.avg_material_at_resign !== null && (
        <p className="mt-2 text-xs text-app-muted">
          Resigns when about {Math.abs(r.avg_material_at_resign).toFixed(1)} points of material down on average.
        </p>
      )}
      <p className={`${eyebrowCls} mb-2 mt-4`}>Draws ({pct(d.draw_rate_pct)} of games)</p>
      {d.by_reason.length ? (
        <ul className="grid gap-1.5 text-xs">
          {d.by_reason.map((row) => (
            <li key={row.reason} className="flex justify-between text-app-muted">
              <span>{REASON_LABEL[row.reason] ?? row.reason}</span>
              <span className="nums text-app-text">
                {row.games} · {pct(row.pct)}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-app-faint">No draws in this sample.</p>
      )}
      {d.agreed_as_favourite > 0 && (
        <p className="mt-2 text-xs text-app-muted">
          Agreed {d.agreed_as_favourite} draw{d.agreed_as_favourite === 1 ? "" : "s"} as the higher-rated player.
        </p>
      )}
    </Sub>
  );
}

function LossEndings({ report }: { report: ScoutingReport }) {
  const p = report.profile;
  return (
    <Sub title="How they lose">
      {p.terminations.loss.length ? (
        <ul className="grid gap-2.5">
          {p.terminations.loss.map((row) => (
            <li key={row.reason}>
              <div className="flex justify-between text-sm">
                <span className="text-app-muted">{REASON_LABEL[row.reason] ?? row.reason}</span>
                <span className="nums text-app-text">
                  {row.games} · {pct(row.pct)}
                </span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
                <div className="h-full rounded-full bg-app-good/70" style={{ width: `${row.pct}%` }} />
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-app-faint">No losses in this sample.</p>
      )}
      <p className="mt-3 text-xs text-app-muted">
        Early collapses (lost within 25 moves):{" "}
        <span className="nums font-semibold text-app-text">{pct(p.overall.early_loss_rate)}</span> of games.
      </p>
      <p className={`${eyebrowCls} mb-2 mt-4`}>Game length</p>
      <div className="grid gap-3">
        {[
          { label: "Up to move 40", stats: p.short_games },
          { label: "Past move 40", stats: p.long_games },
        ].map(({ label, stats }) => (
          <div key={label}>
            <div className="flex items-center justify-between text-sm">
              <span className="text-app-muted">{label}</span>
              <span className="flex items-center gap-2">
                <span className="nums text-xs text-app-faint">{stats.games}g</span>
                <span className="nums font-semibold text-app-text">{pct(stats.score_pct)}</span>
                <Delta value={stats.perf_delta} invert decimals={0} />
              </span>
            </div>
            <WinLossBar wins={stats.wins} draws={stats.draws} losses={stats.losses} className="mt-1.5" />
          </div>
        ))}
      </div>
    </Sub>
  );
}

function ClockTrends({ report }: { report: ScoutingReport }) {
  const p = report.profile;
  return (
    <Sub title="Clock & recent changes">
      <p className="text-sm text-app-muted">
        Uses <span className="nums font-semibold text-app-text">{pct(report.baseline.avg_opening_time_pct, 1)}</span> of their clock by move
        10 on average
        {p.overall.avg_first_think !== null && (
          <>
            ; first long think around move <span className="nums font-semibold text-app-text">{p.overall.avg_first_think.toFixed(0)}</span>
          </>
        )}
        .
      </p>
      {report.recent_changes.length ? (
        <ul className="mt-3 grid gap-1.5">
          {report.recent_changes.map((change) => (
            <li key={`${change.color}-${change.family}-${change.direction}`} className="flex flex-wrap items-center gap-2 text-xs">
              <Badge tone={change.direction === "new" ? "yellow" : "neutral"}>{change.direction === "new" ? "New" : "Dropped"}</Badge>
              <span className="text-app-muted">
                {change.family} as {change.color}: {pct(change.earlier_share)} → {pct(change.recent_share)}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-xs text-app-faint">No recent change in their opening choices.</p>
      )}
    </Sub>
  );
}

export function HabitsPanel({ report }: { report: ScoutingReport }) {
  const h = report.habits;
  if (!h) return null;
  return (
    <Card>
      <CardHeader title="Habits & tendencies" eyebrow="How they behave">
        Splits are their score; green deltas mean they do worse than their rating predicts. Rows with fewer than 5 games are dimmed.
      </CardHeader>
      {h.insights.length > 0 && (
        <div className="mb-5">
          <p className={`${eyebrowCls} mb-2`}>Key takeaways</p>
          <InsightList items={h.insights} />
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        <SessionsTilt h={h} />
        <TimeBlock h={h} />
        <PositionComfort h={h} />
        <ResignDraw h={h} />
        <LossEndings report={report} />
        <ClockTrends report={report} />
      </div>
    </Card>
  );
}
