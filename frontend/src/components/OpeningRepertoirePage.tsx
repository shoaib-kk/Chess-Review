import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  OpeningGameExample,
  OpeningRepertoire,
  OpeningRepertoireRow,
  TimeClassFilter,
} from "../types";

interface OpeningRepertoirePageProps {
  loading: boolean;
  repertoire: OpeningRepertoire | null;
  username: string;
  onUsernameChange: (username: string) => void;
  limit: number;
  onLimitChange: (limit: number) => void;
  timeClass: TimeClassFilter;
  onTimeClassChange: (timeClass: TimeClassFilter) => void;
  ratedOnly: boolean;
  onRatedOnlyChange: (ratedOnly: boolean) => void;
  onFetchRepertoire: (
    username: string,
    params: { limit: number; time_class: TimeClassFilter; rated_only: boolean },
  ) => Promise<OpeningRepertoire | null>;
}

type TabKey = "white" | "black";

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "white", label: "White" },
  { key: "black", label: "Black" },
];

const panel = "bg-app-panel";
const input =
  "h-11 w-full border-[0.5px] border-app-border bg-app-panel px-3 text-sm text-app-text outline-none placeholder:text-app-muted focus:border-app-text";

function fmt(value: number | null | undefined, suffix = "") {
  return value === null || value === undefined ? "-" : `${value.toFixed(1)}${suffix}`;
}

function allRows(repertoire: OpeningRepertoire) {
  return [
    ...repertoire.repertoire.white,
    ...repertoire.repertoire.black,
  ];
}

export function OpeningRepertoirePage({
  loading,
  repertoire,
  username,
  onUsernameChange,
  limit,
  onLimitChange,
  timeClass,
  onTimeClassChange,
  ratedOnly,
  onRatedOnlyChange,
  onFetchRepertoire,
}: OpeningRepertoirePageProps) {
  const [activeTab, setActiveTab] = useState<TabKey>("white");

  const openings = useMemo(() => (repertoire ? allRows(repertoire) : []), [repertoire]);

  async function fetchRepertoire() {
    if (!username.trim()) return;
    await onFetchRepertoire(username.trim(), { limit, time_class: timeClass, rated_only: ratedOnly });
  }

  return (
    <div className="grid gap-5">
      <section className={panel}>
        <div className="border-b border-app-border px-5 py-5">
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">Opening-specific performance</p>
          <h2 className="mt-1 text-2xl font-medium text-app-text">Opening Repertoire</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-app-muted">
            See which openings score best when you play White or Black.
          </p>
        </div>
        <div className="grid gap-3 px-5 py-5 lg:grid-cols-[1fr_120px_150px_auto_auto] lg:items-center">
          <input className={input} value={username} placeholder="Chess.com username" onChange={(event) => onUsernameChange(event.target.value)} />
          <input className={input} type="number" min={20} max={500} value={limit} onChange={(event) => onLimitChange(Number(event.target.value))} />
          <select className={input} value={timeClass} onChange={(event) => onTimeClassChange(event.target.value as TimeClassFilter)}>
            <option value="">All time controls</option>
            <option value="rapid">Rapid</option>
            <option value="blitz">Blitz</option>
            <option value="bullet">Bullet</option>
          </select>
          <label className="flex h-11 items-center gap-2 border-[0.5px] border-app-border bg-app-panel px-3 text-sm text-app-muted">
            <input type="checkbox" className="accent-app-accent" checked={ratedOnly} onChange={(event) => onRatedOnlyChange(event.target.checked)} />
            Rated only
          </label>
          <PlainButton disabled={!username.trim() || loading} onClick={fetchRepertoire}>
            {loading ? "Loading..." : "Refresh Repertoire"}
          </PlainButton>
        </div>
      </section>

      {repertoire ? (
        <>
          <TopSummary repertoire={repertoire} />
          <BestWorst repertoire={repertoire} />
          <MostPlayedChart openings={openings} />
          <section className={panel}>
            <div className="flex flex-wrap gap-2 border-b border-app-border px-5 py-4">
              {TABS.map((tab) => (
                <PlainButton key={tab.key} active={activeTab === tab.key} small onClick={() => setActiveTab(tab.key)}>
                  {tab.label}
                </PlainButton>
              ))}
            </div>
            <OpeningList title={TABS.find((tab) => tab.key === activeTab)?.label ?? "Openings"} rows={repertoire.repertoire[activeTab]} />
          </section>
        </>
      ) : (
        <section className={`${panel} p-5`}>
          <p className="text-sm text-app-muted">{loading ? "Building your repertoire..." : "Enter a Chess.com username to build your opening repertoire."}</p>
        </section>
      )}
    </div>
  );
}

function PlainButton({
  children,
  active = false,
  small = false,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean; small?: boolean }) {
  return (
    <button
      className={`inline-flex items-center justify-center border-b bg-transparent px-3 text-sm font-medium text-app-text transition hover:bg-app-panelSecondary disabled:cursor-not-allowed disabled:text-app-muted ${
        active ? "border-app-text" : "border-transparent"
      } ${small ? "h-8" : "h-11"}`}
      {...props}
    >
      {children}
    </button>
  );
}

function TopSummary({ repertoire }: { repertoire: OpeningRepertoire }) {
  const white = [...repertoire.repertoire.white].sort((a, b) => b.games - a.games)[0] ?? null;
  const black = [
    ...repertoire.repertoire.black_vs_e4,
    ...repertoire.repertoire.black_vs_d4,
    ...repertoire.repertoire.black_vs_other,
  ].sort((a, b) => b.games - a.games)[0] ?? null;

  return (
    <section className={panel}>
      <div className="grid gap-5 px-5 py-5 md:grid-cols-3">
        <SummaryBlock label="Games Analyzed" primary={String(repertoire.summary.total_games)} />
        <SummaryBlock label="Most Played White Opening" primary={white?.opening_name ?? "-"} secondary={white ? `${white.games} games` : undefined} />
        <SummaryBlock label="Most Played Black Defence" primary={black?.opening_name ?? "-"} secondary={black ? `${black.games} games` : undefined} />
      </div>
    </section>
  );
}

function SummaryBlock({ label, primary, secondary }: { label: string; primary: string; secondary?: string }) {
  return (
    <div className="min-w-0 md:border-l md:border-app-border md:pl-5 first:md:border-l-0 first:md:pl-0">
      <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">{label}</p>
      <p className="mt-2 text-xl font-medium text-app-text">{primary}</p>
      {secondary && <p className="mt-1 font-mono text-sm text-app-muted">{secondary}</p>}
    </div>
  );
}

function BestWorst({ repertoire }: { repertoire: OpeningRepertoire }) {
  const best = (repertoire.recommendations.strongest_openings.length
    ? repertoire.recommendations.strongest_openings
    : repertoire.summary.strongest_opening ? [repertoire.summary.strongest_opening] : []
  ).slice(0, 3);
  const worst = (repertoire.recommendations.weakest_openings.length
    ? repertoire.recommendations.weakest_openings
    : repertoire.summary.weakest_opening ? [repertoire.summary.weakest_opening] : []
  ).slice(0, 3);

  return (
    <section className={panel}>
      <div className="grid gap-6 px-5 py-5 xl:grid-cols-2">
        <OpeningInsightList title="Best Performing Openings" marker="+" rows={best} />
        <OpeningInsightList title="Needs Improvement" marker="!" rows={worst} />
      </div>
    </section>
  );
}

function OpeningInsightList({ title, marker, rows }: { title: string; marker: string; rows: OpeningRepertoireRow[] }) {
  return (
    <div>
      <h3 className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">{title}</h3>
      <div className="mt-4 grid gap-3">
        {rows.length ? rows.map((row) => (
          <div key={`${title}-${row.id}`} className="grid grid-cols-[28px_1fr] gap-3 border-b border-app-border/70 pb-3">
            <span className="font-mono text-lg text-app-text">{marker}</span>
            <div className="min-w-0">
              <p className="text-base font-medium text-app-text">{row.opening_name}</p>
              <p className="mt-1 font-mono text-sm text-app-muted">
                {fmt(row.win_rate, "%")} Win Rate - {fmt(row.avg_accuracy)} Accuracy - {row.games} Games
              </p>
            </div>
          </div>
        )) : <p className="text-sm text-app-muted">More games are needed before this section is reliable.</p>}
      </div>
    </div>
  );
}

function MostPlayedChart({ openings }: { openings: OpeningRepertoireRow[] }) {
  const data = [...openings].sort((a, b) => b.games - a.games).slice(0, 10);
  const height = Math.max(320, data.length * 40 + 48);

  return (
    <section className={`${panel} px-5 py-5`}>
      <h3 className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">Top 10 Most Played Openings</h3>
      <div className="mt-5">
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} layout="vertical" margin={{ left: 12, right: 28, top: 8, bottom: 8 }}>
            <CartesianGrid stroke="#263244" horizontal={false} />
            <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
            <YAxis
              type="category"
              dataKey="opening_name"
              width={260}
              tick={{ fill: "#f8fafc", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              interval={0}
            />
            <Tooltip contentStyle={{ background: "#111827", border: "1px solid #263244", color: "#f8fafc" }} />
            <Bar dataKey="games" fill="#3b82f6" barSize={22} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function OpeningList({ title, rows }: { title: string; rows: OpeningRepertoireRow[] }) {
  const sorted = [...rows].sort((a, b) => b.win_rate - a.win_rate || b.games - a.games || a.opening_name.localeCompare(b.opening_name));

  return (
    <div className="px-5 py-5">
      <h3 className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">{title} - Best Win Rates</h3>
      <div className="mt-4 grid gap-2">
        {sorted.map((row) => <OpeningRow key={row.id} row={row} />)}
        {!sorted.length && <p className="text-sm text-app-muted">No openings in this category for the selected filters.</p>}
      </div>
    </div>
  );
}

function OpeningRow({ row }: { row: OpeningRepertoireRow }) {
  return (
    <details className="group border-b border-app-border/70 py-4">
      <summary className="grid cursor-pointer list-none gap-3 md:grid-cols-[1fr_auto] md:items-start">
        <div className="min-w-0">
          <p className="text-base font-medium text-app-text">{row.opening_name}</p>
          <p className="mt-1 text-sm text-app-muted">{row.eco}</p>
        </div>
        <div className="grid grid-cols-2 gap-x-5 gap-y-2 font-mono text-sm text-app-text sm:grid-cols-3">
          <SmallMetric label="Games" value={String(row.games)} />
          <SmallMetric label="Win Rate" value={fmt(row.win_rate, "%")} />
          <SmallMetric label="Accuracy" value={fmt(row.avg_accuracy, "%")} />
        </div>
      </summary>
      <div className="mt-4 grid gap-4 text-sm text-app-muted lg:grid-cols-4">
        <DetailList title="Variations" rows={row.variations.map((item) => `${item.variation}: ${item.games} games (${item.frequency}%)`)} />
        <DetailList title="Typical results" rows={row.typical_results.map((item) => `${item.result}: ${item.games} games (${item.frequency}%)`)} />
        <GameList title="Best examples" rows={row.best_example_games} />
        <GameList title="Recent games" rows={row.recent_games} />
      </div>
    </details>
  );
}

function SmallMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-right">
      <p className="text-[10px] uppercase tracking-[0.12em] text-app-muted">{label}</p>
      <p className="mt-1">{value}</p>
    </div>
  );
}

function DetailList({ title, rows }: { title: string; rows: string[] }) {
  return (
    <div>
      <p className="font-medium text-app-text">{title}</p>
      <div className="mt-2 grid gap-1">
        {rows.length ? rows.map((row) => <p key={row}>{row}</p>) : <p>No data yet.</p>}
      </div>
    </div>
  );
}

function GameList({ title, rows }: { title: string; rows: OpeningGameExample[] }) {
  return (
    <div>
      <p className="font-medium text-app-text">{title}</p>
      <div className="mt-2 grid gap-1">
        {rows.length ? rows.slice(0, 3).map((row, index) => (
          <GameLink key={`${title}-${row.url ?? index}`} row={row}>
            {row.date ?? "Unknown date"} vs {row.opponent} - {row.result}
          </GameLink>
        )) : <p>No games available.</p>}
      </div>
    </div>
  );
}

function GameLink({ row, children }: { row: OpeningGameExample; children: ReactNode }) {
  if (!row.url) return <p>{children}</p>;
  return (
    <a className="transition hover:text-app-text" href={row.url} target="_blank" rel="noreferrer">
      {children}
    </a>
  );
}
