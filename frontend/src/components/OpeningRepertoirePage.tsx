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
import { openingFamily } from "../utils/openingFamilies";

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
  { key: "white", label: "As White" },
  { key: "black", label: "As Black" },
];

const panel = "bg-app-panel";
const input =
  "h-11 w-full bg-app-panelSecondary px-3 text-sm text-app-text outline-none transition placeholder:text-app-muted focus:bg-[#3c3c3c]";

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
  const [openingSearch, setOpeningSearch] = useState("");

  const grouped = useMemo(() => {
    if (!repertoire) return null;
    return {
      white: groupRowsByFamily(repertoire.repertoire.white),
      black: groupRowsByFamily(repertoire.repertoire.black),
      all: groupRowsByFamily(allRows(repertoire)),
    };
  }, [repertoire]);
  const openings = grouped?.all ?? [];

  async function fetchRepertoire() {
    if (!username.trim()) return;
    await onFetchRepertoire(username.trim(), { limit, time_class: timeClass, rated_only: ratedOnly });
  }

  return (
    <div className="grid gap-5">
      <section className={panel}>
        <div className="px-5 py-6">
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
          <label className="flex h-11 items-center gap-2 bg-app-panelSecondary px-3 text-sm text-app-muted">
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
          <TopSummary repertoire={repertoire} whiteRows={grouped?.white ?? []} blackRows={grouped?.black ?? []} />
          <BestWorst rows={openings} />
          <MostPlayedChart whiteRows={grouped?.white ?? []} blackRows={grouped?.black ?? []} />
          <section className={panel}>
            <div className="grid gap-4 px-5 py-5 lg:grid-cols-[auto_1fr] lg:items-center">
              <div className="flex flex-wrap gap-2">
                {TABS.map((tab) => (
                  <PlainButton key={tab.key} active={activeTab === tab.key} small onClick={() => setActiveTab(tab.key)}>
                    {tab.label}
                  </PlainButton>
                ))}
              </div>
              <input
                className={input}
                value={openingSearch}
                placeholder="Search openings to see win rate..."
                onChange={(event) => setOpeningSearch(event.target.value)}
              />
            </div>
            <OpeningList title={TABS.find((tab) => tab.key === activeTab)?.label ?? "Openings"} rows={grouped?.[activeTab] ?? []} search={openingSearch} />
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

function groupRowsByFamily(rows: OpeningRepertoireRow[]) {
  const groups = new Map<string, OpeningRepertoireRow>();

  for (const row of rows) {
    const family = openingFamily(row.opening_family, row.opening_name);
    const existing = groups.get(family);

    if (!existing) {
      groups.set(family, {
        ...row,
        id: `${row.category}::${family}`,
        opening_name: family,
        opening_family: family,
        variation: null,
      });
      continue;
    }

    const games = existing.games + row.games;
    const wins = existing.wins + row.wins;
    const losses = existing.losses + row.losses;
    const draws = existing.draws + row.draws;

    existing.games = games;
    existing.frequency += row.frequency;
    existing.wins = wins;
    existing.losses = losses;
    existing.draws = draws;
    existing.win_rate = percent(wins, games);
    existing.avg_accuracy = weightedAverage(existing.avg_accuracy, existing.games - row.games, row.avg_accuracy, row.games);
    existing.avg_cp_loss = weightedAverage(existing.avg_cp_loss, existing.games - row.games, row.avg_cp_loss, row.games);
    existing.avg_game_length = weightedAverage(existing.avg_game_length, existing.games - row.games, row.avg_game_length, row.games);
    existing.variations = mergeVariations(existing.variations, row.variations, games);
    existing.recent_games = [...existing.recent_games, ...row.recent_games].slice(0, 8);
    existing.common_opponent_responses = [...existing.common_opponent_responses, ...row.common_opponent_responses];
    existing.typical_results = mergeResults(existing.typical_results, row.typical_results, games);
    existing.best_example_games = [...existing.best_example_games, ...row.best_example_games].slice(0, 5);
    existing.worst_example_games = [...existing.worst_example_games, ...row.worst_example_games].slice(0, 5);
  }

  return [...groups.values()];
}

function percent(part: number, whole: number) {
  return whole ? Math.round((part / whole) * 1000) / 10 : 0;
}

function weightedAverage(left: number | null, leftCount: number, right: number | null, rightCount: number) {
  const total = (left === null ? 0 : leftCount) + (right === null ? 0 : rightCount);
  if (!total) return null;
  const value = ((left ?? 0) * (left === null ? 0 : leftCount) + (right ?? 0) * (right === null ? 0 : rightCount)) / total;
  return Math.round(value * 10) / 10;
}

function mergeVariations(left: OpeningRepertoireRow["variations"], right: OpeningRepertoireRow["variations"], totalGames: number) {
  const counts = new Map<string, { variation: string; games: number; eco: string }>();
  for (const item of [...left, ...right]) {
    const existing = counts.get(item.variation);
    if (existing) existing.games += item.games;
    else counts.set(item.variation, { variation: item.variation, games: item.games, eco: item.eco });
  }
  return [...counts.values()]
    .sort((a, b) => b.games - a.games || a.variation.localeCompare(b.variation))
    .map((item) => ({ ...item, frequency: percent(item.games, totalGames) }));
}

function mergeResults(left: OpeningRepertoireRow["typical_results"], right: OpeningRepertoireRow["typical_results"], totalGames: number) {
  const counts = new Map<string, { result: OpeningRepertoireRow["typical_results"][number]["result"]; games: number }>();
  for (const item of [...left, ...right]) {
    const existing = counts.get(item.result);
    if (existing) existing.games += item.games;
    else counts.set(item.result, { result: item.result, games: item.games });
  }
  return [...counts.values()]
    .sort((a, b) => b.games - a.games)
    .map((item) => ({ ...item, frequency: percent(item.games, totalGames) }));
}

function PlainButton({
  children,
  active = false,
  small = false,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean; small?: boolean }) {
  return (
    <button
      className={`inline-flex items-center justify-center bg-transparent px-3 text-sm font-medium text-app-text transition hover:bg-app-panelSecondary disabled:cursor-not-allowed disabled:text-app-muted ${
        active ? "bg-app-panelSecondary" : ""
      } ${small ? "h-8" : "h-11"}`}
      {...props}
    >
      {children}
    </button>
  );
}

function TopSummary({ repertoire, whiteRows, blackRows }: { repertoire: OpeningRepertoire; whiteRows: OpeningRepertoireRow[]; blackRows: OpeningRepertoireRow[] }) {
  const white = [...whiteRows].sort((a, b) => b.games - a.games)[0] ?? null;
  const black = [...blackRows].sort((a, b) => b.games - a.games)[0] ?? null;

  return (
    <section className={panel}>
      <div className="grid gap-5 px-5 py-5 md:grid-cols-3">
        <SummaryBlock label="Games Analyzed" primary={String(repertoire.summary.total_games)} />
        <SummaryBlock label="Most Played as White" primary={white?.opening_name ?? "-"} secondary={white ? `${white.games} games` : undefined} />
        <SummaryBlock label="Most Played as Black" primary={black?.opening_name ?? "-"} secondary={black ? `${black.games} games` : undefined} />
      </div>
    </section>
  );
}

function SummaryBlock({ label, primary, secondary }: { label: string; primary: string; secondary?: string }) {
  return (
    <div className="min-w-0 md:pl-2 first:md:pl-0">
      <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">{label}</p>
      <p className="mt-2 text-xl font-medium text-app-text">{primary}</p>
      {secondary && <p className="mt-1 font-mono text-sm text-app-muted">{secondary}</p>}
    </div>
  );
}

function BestWorst({ rows }: { rows: OpeningRepertoireRow[] }) {
  const best = [...rows].sort((a, b) => b.win_rate - a.win_rate || b.games - a.games).slice(0, 3);
  const worst = [...rows].sort((a, b) => a.win_rate - b.win_rate || b.games - a.games).slice(0, 3);

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
          <div key={`${title}-${row.id}`} className="grid grid-cols-[28px_1fr] gap-3 pb-3">
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

function MostPlayedChart({ whiteRows, blackRows }: { whiteRows: OpeningRepertoireRow[]; blackRows: OpeningRepertoireRow[] }) {
  const data = familyChartRows(whiteRows, blackRows).sort((a, b) => b.games - a.games || a.opening_name.localeCompare(b.opening_name)).slice(0, 10);
  const height = Math.max(320, data.length * 40 + 48);

  return (
    <section className={`${panel} px-5 py-5`}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h3 className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">Top 10 Most Played Opening Families</h3>
        <div className="flex gap-4 text-xs text-app-muted">
          <span className="inline-flex items-center gap-2"><span className="inline-block h-2 w-2 bg-app-accent" />As White</span>
          <span className="inline-flex items-center gap-2"><span className="inline-block h-2 w-2 bg-[#4b4b4b]" />As Black</span>
        </div>
      </div>
      <div className="mt-5">
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} layout="vertical" margin={{ left: 12, right: 28, top: 8, bottom: 8 }}>
            <CartesianGrid stroke="#343434" horizontal={false} />
            <XAxis type="number" tick={{ fill: "#8a8a8a", fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
            <YAxis
              type="category"
              dataKey="opening_name"
              width={260}
              tick={{ fill: "#d4d4d4", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              interval={0}
            />
            <Tooltip
              contentStyle={{ background: "#1f1f1f", border: "none", color: "#d4d4d4" }}
              formatter={(value, name, props) => {
                const payload = props.payload as { games: number };
                if (name === "Total") return [`${value}`, "Total games"];
                return [`${value}`, `${name} (${payload.games} total)`];
              }}
            />
            <Bar dataKey="whiteGames" stackId="games" fill="#007acc" barSize={22} name="As White" />
            <Bar dataKey="blackGames" stackId="games" fill="#4b4b4b" barSize={22} name="As Black" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function familyChartRows(whiteRows: OpeningRepertoireRow[], blackRows: OpeningRepertoireRow[]) {
  const groups = new Map<string, { opening_name: string; games: number; whiteGames: number; blackGames: number }>();

  for (const row of whiteRows) {
    const family = openingFamily(row.opening_family, row.opening_name);
    const existing = groups.get(family);
    if (existing) {
      existing.games += row.games;
      existing.whiteGames += row.games;
    } else {
      groups.set(family, { opening_name: family, games: row.games, whiteGames: row.games, blackGames: 0 });
    }
  }

  for (const row of blackRows) {
    const family = openingFamily(row.opening_family, row.opening_name);
    const existing = groups.get(family);
    if (existing) {
      existing.games += row.games;
      existing.blackGames += row.games;
    } else {
      groups.set(family, { opening_name: family, games: row.games, whiteGames: 0, blackGames: row.games });
    }
  }

  return [...groups.values()];
}

function OpeningList({ title, rows, search }: { title: string; rows: OpeningRepertoireRow[]; search: string }) {
  const query = search.trim().toLowerCase();
  const filtered = query
    ? rows.filter((row) =>
        [
          row.opening_name,
          row.opening_family,
          row.eco,
          ...row.variations.map((item) => item.variation),
        ].join(" ").toLowerCase().includes(query),
      )
    : rows;
  const sorted = [...filtered].sort((a, b) => b.win_rate - a.win_rate || b.games - a.games || a.opening_name.localeCompare(b.opening_name));

  return (
    <div className="px-5 py-5">
      <h3 className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">{title} - Best Win Rates</h3>
      <div className="mt-4 grid gap-2">
        {sorted.map((row) => <OpeningRow key={row.id} row={row} />)}
        {!sorted.length && (
          <p className="text-sm text-app-muted">
            {query ? "No matching openings found for this side." : "No openings in this category for the selected filters."}
          </p>
        )}
      </div>
    </div>
  );
}

function OpeningRow({ row }: { row: OpeningRepertoireRow }) {
  return (
    <details className="group py-5">
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
