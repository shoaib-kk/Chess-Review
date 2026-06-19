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
import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  CircleAlert,
  Filter,
  Search,
  Trophy,
} from "lucide-react";
import type {
  OpeningGameExample,
  OpeningRepertoire,
  OpeningRepertoireRow,
  TimeClassFilter,
} from "../types";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";
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

const input =
  "h-11 w-full rounded-lg border border-app-border bg-app-panelSecondary px-3 text-sm text-app-text outline-none transition placeholder:text-app-muted focus-visible:border-app-accent focus-visible:ring-2 focus-visible:ring-app-accent/50";

function fmt(value: number | null | undefined, suffix = "") {
  return value === null || value === undefined ? "-" : `${value.toFixed(1)}${suffix}`;
}

function allRows(repertoire: OpeningRepertoire) {
  return [
    ...repertoire.repertoire.white,
    ...repertoire.repertoire.black,
  ];
}

function hasInvalidOpeningName(row: OpeningRepertoireRow) {
  const invalidNames = new Set(["undefined", "undeefined"]);
  return [row.opening_name, row.opening_family].some((name) =>
    invalidNames.has((name ?? "").trim().toLowerCase()),
  );
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
  const [detailFamily, setDetailFamily] = useState<string | null>(null);

  const grouped = useMemo(() => {
    if (!repertoire) return null;
    return {
      white: groupRowsByFamily(repertoire.repertoire.white),
      black: groupRowsByFamily(repertoire.repertoire.black),
      all: groupRowsByFamily(allRows(repertoire)),
    };
  }, [repertoire]);
  const openings = grouped?.all ?? [];

  const detailRow = detailFamily ? openings.find((row) => row.opening_name === detailFamily) ?? null : null;
  const detailWhite = detailFamily && grouped ? grouped.white.find((row) => row.opening_name === detailFamily) ?? null : null;
  const detailBlack = detailFamily && grouped ? grouped.black.find((row) => row.opening_name === detailFamily) ?? null : null;

  async function fetchRepertoire() {
    if (!username.trim()) return;
    setDetailFamily(null);
    await onFetchRepertoire(username.trim(), { limit, time_class: timeClass, rated_only: ratedOnly });
  }

  if (detailRow) {
    return (
      <div className="grid animate-fade-in gap-5">
        <OpeningDetail row={detailRow} whiteRow={detailWhite} blackRow={detailBlack} onBack={() => setDetailFamily(null)} />
      </div>
    );
  }

  return (
    <div className="grid animate-fade-in gap-5">
      <Card>
        <CardHeader title="Opening Repertoire" eyebrow="Opening-specific performance">
          See which openings score best when you play White or Black.
        </CardHeader>
        <div className="grid gap-3 lg:grid-cols-[1fr_120px_150px_auto_auto] lg:items-center">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-app-faint" />
            <input className={`${input} pl-9`} value={username} placeholder="Chess.com username" onChange={(event) => onUsernameChange(event.target.value)} />
          </div>
          <input className={`${input} font-mono`} type="number" min={20} max={500} value={limit} onChange={(event) => onLimitChange(Number(event.target.value))} />
          <select className={input} value={timeClass} onChange={(event) => onTimeClassChange(event.target.value as TimeClassFilter)}>
            <option value="">All time controls</option>
            <option value="rapid">Rapid</option>
            <option value="blitz">Blitz</option>
            <option value="bullet">Bullet</option>
          </select>
          <label className="flex h-11 cursor-pointer items-center gap-2 rounded-lg border border-app-border bg-app-panelSecondary px-3 text-sm text-app-muted transition hover:bg-app-panelHover">
            <input type="checkbox" className="h-4 w-4 accent-app-accent" checked={ratedOnly} onChange={(event) => onRatedOnlyChange(event.target.checked)} />
            Rated only
          </label>
          <Button variant="primary" disabled={!username.trim() || loading} onClick={fetchRepertoire}>
            <Filter className="h-4 w-4" />
            {loading ? "Reading public games..." : "Refresh Repertoire"}
          </Button>
        </div>
      </Card>

      {repertoire ? (
        <>
          <TopSummary repertoire={repertoire} whiteRows={grouped?.white ?? []} blackRows={grouped?.black ?? []} />
          <BestWorst rows={openings} />
          <MostPlayedChart whiteRows={grouped?.white ?? []} blackRows={grouped?.black ?? []} onSelect={setDetailFamily} />
          <Card>
            <div className="grid gap-3 pb-4 lg:grid-cols-[auto_1fr] lg:items-center">
              <div className="inline-flex rounded-lg border border-app-border bg-app-panelSecondary p-1">
                {TABS.map((tab) => (
                  <SegmentButton key={tab.key} active={activeTab === tab.key} onClick={() => setActiveTab(tab.key)}>
                    {tab.label}
                  </SegmentButton>
                ))}
              </div>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-app-faint" />
                <input
                  className={`${input} pl-9`}
                  value={openingSearch}
                  placeholder="Search openings to see win rate..."
                  onChange={(event) => setOpeningSearch(event.target.value)}
                />
              </div>
            </div>
            <OpeningList title={TABS.find((tab) => tab.key === activeTab)?.label ?? "Openings"} rows={grouped?.[activeTab] ?? []} search={openingSearch} />
          </Card>
        </>
      ) : (
        <Card>
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <div className="grid h-11 w-11 place-items-center rounded-full bg-app-panelSecondary text-app-muted">
              <BookOpen className="h-5 w-5" />
            </div>
            <p className="text-sm text-app-muted">{loading ? "Reading public games and grouping openings..." : "Enter a Chess.com username to build your opening repertoire."}</p>
          </div>
        </Card>
      )}
    </div>
  );
}

function groupRowsByFamily(rows: OpeningRepertoireRow[]) {
  const groups = new Map<string, OpeningRepertoireRow>();

  for (const row of rows) {
    if (hasInvalidOpeningName(row)) continue;

    const family = openingFamily(row.opening_family, row.opening_name);
    if (["undefined", "undeefined"].includes(family.trim().toLowerCase())) continue;

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

function SegmentButton({
  children,
  active = false,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      className={`inline-flex h-8 items-center justify-center rounded-md px-4 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-app-accent/50 disabled:cursor-not-allowed ${
        active ? "bg-app-accentSoft text-app-text" : "text-app-muted hover:text-app-text"
      }`}
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
    <div className="grid gap-6 sm:grid-cols-3 sm:divide-x sm:divide-app-border">
      <SummaryBlock label="Games Analyzed" primary={String(repertoire.summary.total_games)} mono />
      <SummaryBlock label="Most Played as White" primary={white?.opening_name ?? "-"} secondary={white ? `${white.games} games` : undefined} />
      <SummaryBlock label="Most Played as Black" primary={black?.opening_name ?? "-"} secondary={black ? `${black.games} games` : undefined} />
    </div>
  );
}

function SummaryBlock({ label, primary, secondary, mono = false }: { label: string; primary: string; secondary?: string; mono?: boolean }) {
  return (
    <div className="min-w-0 sm:[&:not(:first-child)]:pl-6">
      <p className="text-xs font-medium uppercase tracking-wide text-app-faint">{label}</p>
      <p className={`mt-2 break-words text-xl font-semibold leading-snug text-app-text ${mono ? "font-mono" : ""}`}>{primary}</p>
      {secondary && <p className="mt-1 font-mono text-sm text-app-muted">{secondary}</p>}
    </div>
  );
}

function BestWorst({ rows }: { rows: OpeningRepertoireRow[] }) {
  const best = [...rows].sort((a, b) => b.win_rate - a.win_rate || b.games - a.games).slice(0, 3);
  const worst = [...rows].sort((a, b) => a.win_rate - b.win_rate || b.games - a.games).slice(0, 3);

  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <Card>
        <CardHeader title="Best Performing Openings" eyebrow="Strengths" />
        <div>
          <OpeningInsightList tone="good" rows={best} />
        </div>
      </Card>
      <Card>
        <CardHeader title="Needs Improvement" eyebrow="Study priorities" />
        <div>
          <OpeningInsightList tone="blunder" rows={worst} />
        </div>
      </Card>
    </div>
  );
}

function OpeningInsightList({ tone, rows }: { tone: "good" | "blunder"; rows: OpeningRepertoireRow[] }) {
  if (!rows.length) {
    return <p className="text-sm text-app-muted">More games are needed before this section is reliable.</p>;
  }

  const Icon = tone === "good" ? Trophy : CircleAlert;
  const iconClass = tone === "good" ? "text-app-good" : "text-app-blunder";
  const tintClass = tone === "good" ? "bg-app-good/10" : "bg-app-blunder/10";

  return (
    <div className="grid gap-3">
      {rows.map((row) => (
        <div
          key={`${tone}-${row.id}`}
          className="flex items-start gap-3 border-b border-app-border py-3 last:border-b-0"
        >
          <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${tintClass} ${iconClass}`}>
            <Icon className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <p className="break-words text-sm font-medium leading-snug text-app-text">{row.opening_name}</p>
            <p className="mt-1 font-mono text-xs text-app-muted">
              {fmt(row.win_rate, "%")} Win Rate - {row.games} Games
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

function MostPlayedChart({
  whiteRows,
  blackRows,
  onSelect,
}: {
  whiteRows: OpeningRepertoireRow[];
  blackRows: OpeningRepertoireRow[];
  onSelect: (family: string) => void;
}) {
  const data = familyChartRows(whiteRows, blackRows).sort((a, b) => b.games - a.games || a.opening_name.localeCompare(b.opening_name)).slice(0, 10);
  const height = Math.max(320, data.length * 40 + 48);

  function handleChartClick(state: { activeLabel?: string; activePayload?: Array<{ payload?: { opening_name?: string } }> }) {
    const family = state?.activeLabel ?? state?.activePayload?.[0]?.payload?.opening_name;
    if (family) onSelect(String(family));
  }

  return (
    <Card>
      <CardHeader
        title="Top 10 Most Played Openings"
        eyebrow="Distribution"
        action={
          <div className="flex gap-4 text-xs text-app-muted">
            <span className="inline-flex items-center gap-2"><span className="inline-block h-2 w-2 rounded-full bg-app-accent" />As White</span>
            <span className="inline-flex items-center gap-2"><span className="inline-block h-2 w-2 rounded-full bg-app-borderStrong" />As Black</span>
          </div>
        }
      />
      <div>
        <p className="mb-3 text-xs text-app-muted">Click a bar to open detailed stats for that opening.</p>
        <div className="cursor-pointer overflow-x-auto">
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} layout="vertical" margin={{ left: 12, right: 28, top: 8, bottom: 8 }} onClick={handleChartClick}>
            <CartesianGrid stroke="#222328" horizontal={false} />
            <XAxis type="number" tick={{ fill: "#85868f", fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
            <YAxis
              type="category"
              dataKey="opening_name"
              width={260}
              tick={{ fill: "#f3f3f5", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              interval={0}
            />
            <Tooltip
              cursor={{ fill: "rgba(200,161,90,0.08)" }}
              contentStyle={{ background: "#191a1e", border: "1px solid #34363d", borderRadius: 10, color: "#f3f3f5", boxShadow: "0 16px 48px -16px rgba(0,0,0,0.7)" }}
              labelStyle={{ color: "#f3f3f5" }}
              itemStyle={{ color: "#f3f3f5" }}
              formatter={(value, name, props) => {
                const payload = props.payload as { games: number };
                if (name === "Total") return [`${value}`, "Total games"];
                return [`${value}`, `${name} (${payload.games} total)`];
              }}
            />
            <Bar dataKey="whiteGames" stackId="games" fill="#c8a15a" barSize={22} name="As White" radius={[0, 0, 0, 0]} />
            <Bar dataKey="blackGames" stackId="games" fill="#34363d" barSize={22} name="As Black" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
        </div>
      </div>
    </Card>
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
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-app-faint">{title} - Best Win Rates</h3>
      {sorted.length ? (
        <div className="mt-4 overflow-hidden rounded-lg divide-y divide-app-border">
          {sorted.map((row) => <OpeningRow key={row.id} row={row} />)}
        </div>
      ) : (
        <p className="mt-4 text-sm text-app-muted">
          {query ? "No matching openings found for this side." : "No openings in this category for the selected filters."}
        </p>
      )}
    </div>
  );
}

function OpeningRow({ row }: { row: OpeningRepertoireRow }) {
  return (
    <details className="group transition open:bg-app-accentSoft hover:bg-app-panelSecondary open:hover:bg-app-accentSoft">
      <summary className="grid cursor-pointer list-none gap-3 px-4 py-4 md:grid-cols-[1fr_auto] md:items-center">
        <div className="flex min-w-0 items-center gap-3">
          <ChevronRight className="h-4 w-4 shrink-0 text-app-faint transition group-open:rotate-90" />
          <div className="min-w-0">
            <p className="break-words text-sm font-medium leading-snug text-app-text">{row.opening_name}</p>
            {row.eco && <p className="mt-0.5 text-xs text-app-muted">Code {row.eco}</p>}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-x-5 gap-y-2 pl-7 font-mono text-sm text-app-text md:pl-0">
          <SmallMetric label="Games" value={String(row.games)} />
          <SmallMetric label="Win Rate" value={fmt(row.win_rate, "%")} />
        </div>
      </summary>
      <div className="grid gap-4 px-4 py-4 text-sm text-app-muted lg:grid-cols-3">
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
      <p className="text-[10px] font-medium uppercase tracking-wide text-app-muted">{label}</p>
      <p className="mt-1 text-app-text">{value}</p>
    </div>
  );
}

function DetailList({ title, rows }: { title: string; rows: string[] }) {
  return (
    <div>
      {title && <p className="text-xs font-semibold uppercase tracking-wide text-app-faint">{title}</p>}
      <div className={`grid gap-1 ${title ? "mt-2" : ""}`}>
        {rows.length ? rows.map((row) => <p key={row} className="text-app-muted">{row}</p>) : <p className="text-app-faint">No data yet.</p>}
      </div>
    </div>
  );
}

function WinLossBar({ wins, draws, losses, className = "h-3" }: { wins: number; draws: number; losses: number; className?: string }) {
  const total = wins + draws + losses || 1;
  const pct = (value: number) => `${(value / total) * 100}%`;
  return (
    <div className={`flex w-full overflow-hidden rounded-full bg-app-panelSecondary ring-1 ring-inset ring-app-border ${className}`}>
      <div className="bg-app-good" style={{ width: pct(wins) }} title={`${wins} wins`} />
      <div className="bg-app-borderStrong" style={{ width: pct(draws) }} title={`${draws} draws`} />
      <div className="bg-app-blunder" style={{ width: pct(losses) }} title={`${losses} losses`} />
    </div>
  );
}

function ColorSplitRow({ label, row }: { label: string; row: OpeningRepertoireRow | null }) {
  const side = label.replace(/^As /, "").toLowerCase();
  return (
    <div className="grid items-center gap-x-5 gap-y-2 py-3 sm:grid-cols-[5.5rem_auto_1fr] sm:gap-y-0">
      <span className="text-sm font-medium text-app-text">{label}</span>
      {row ? (
        <>
          <span className="font-mono text-sm font-semibold text-app-text sm:text-right">{fmt(row.win_rate, "%")}</span>
          <div className="flex min-w-0 items-center gap-3">
            <WinLossBar wins={row.wins} draws={row.draws} losses={row.losses} className="h-2 max-w-[180px] flex-1" />
            <span className="shrink-0 font-mono text-xs text-app-muted">
              <span className="text-app-good">{row.wins}W</span>
              <span className="mx-1.5 text-app-faint">/</span>
              <span className="text-app-muted">{row.draws}D</span>
              <span className="mx-1.5 text-app-faint">/</span>
              <span className="text-app-blunder">{row.losses}L</span>
            </span>
          </div>
        </>
      ) : (
        <span className="text-sm text-app-faint sm:col-span-2">No games with this opening as {side}.</span>
      )}
    </div>
  );
}

function OpeningDetail({
  row,
  whiteRow,
  blackRow,
  onBack,
}: {
  row: OpeningRepertoireRow;
  whiteRow: OpeningRepertoireRow | null;
  blackRow: OpeningRepertoireRow | null;
  onBack: () => void;
}) {
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3 pb-5">
        <div className="flex min-w-0 items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBack}>
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">Opening detail</p>
            <h2 className="break-words text-lg font-semibold leading-snug text-app-text">{row.opening_name}</h2>
          </div>
        </div>
        <span className="rounded-full bg-app-panelSecondary px-3 py-1 font-mono text-xs text-app-muted ring-1 ring-inset ring-app-border">
          {row.eco ? `Code ${row.eco}` : "No code"}
        </span>
      </div>

      <div className="border-t border-app-border py-6">
        {/* Focal point: overall win/loss record */}
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-app-muted">Win rate</p>
            <p className="mt-1 font-mono text-5xl font-semibold leading-none text-app-text">{fmt(row.win_rate, "%")}</p>
          </div>
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 font-mono text-sm">
            <span className="text-app-good">{row.wins}W</span>
            <span className="text-app-muted">{row.draws}D</span>
            <span className="text-app-blunder">{row.losses}L</span>
            <span className="text-app-faint">across {row.games} games</span>
          </div>
        </div>
        <div className="mt-4">
          <WinLossBar wins={row.wins} draws={row.draws} losses={row.losses} className="h-4" />
        </div>
      </div>

      {/* Color split, shown inline */}
      <div className="border-t border-app-border py-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">By color</p>
        <div className="mt-2 divide-y divide-app-border">
          <ColorSplitRow label="As White" row={whiteRow} />
          <ColorSplitRow label="As Black" row={blackRow} />
        </div>
      </div>

      {/* Example games */}
      <div className="border-t border-app-border py-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">Example games</p>
        <div className="mt-4 grid gap-5 lg:grid-cols-3">
          <GameList title="Best examples" rows={row.best_example_games} />
          <GameList title="Worst examples" rows={row.worst_example_games} />
          <GameList title="Recent games" rows={row.recent_games} />
        </div>
      </div>
    </Card>
  );
}

function GameList({ title, rows }: { title: string; rows: OpeningGameExample[] }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-app-faint">{title}</p>
      <div className="mt-2 grid gap-1">
        {rows.length ? rows.slice(0, 3).map((row, index) => (
          <GameLink key={`${title}-${row.url ?? index}`} row={row}>
            {row.date ?? "Unknown date"} vs {row.opponent} - {row.result}
          </GameLink>
        )) : <p className="text-app-faint">No games available.</p>}
      </div>
    </div>
  );
}

function GameLink({ row, children }: { row: OpeningGameExample; children: ReactNode }) {
  if (!row.url) return <p className="text-app-muted">{children}</p>;
  return (
    <a className="inline-flex items-center gap-1 text-app-muted transition hover:text-app-accent" href={row.url} target="_blank" rel="noreferrer">
      {children}
      <ArrowUpRight className="h-3 w-3 shrink-0" />
    </a>
  );
}
