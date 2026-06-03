import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  OpeningGameExample,
  OpeningRepertoire,
  OpeningRepertoireRow,
  OpeningTrendPoint,
  RepertoireCategory,
  TimeClassFilter,
} from "../types";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";

interface OpeningRepertoirePageProps {
  loading: boolean;
  onFetchRepertoire: (
    username: string,
    params: { limit: number; time_class: TimeClassFilter; rated_only: boolean },
  ) => Promise<OpeningRepertoire | null>;
  initialUsername?: string | null;
}

type TabKey = RepertoireCategory | "trends";
type TrendWindowKey = "last_30" | "last_90" | "last_180" | "all";

const TAB_LABELS: Record<TabKey, string> = {
  white: "White",
  black_vs_e4: "Black vs e4",
  black_vs_d4: "Black vs d4",
  black_vs_other: "Black vs Other",
  trends: "Trends",
};

function fmt(value: number | null | undefined, suffix = "") {
  return value === null || value === undefined ? "-" : `${value.toFixed(1)}${suffix}`;
}

function shortName(value: string) {
  return value.length > 24 ? `${value.slice(0, 24)}...` : value;
}

export function OpeningRepertoirePage({ loading, onFetchRepertoire, initialUsername }: OpeningRepertoirePageProps) {
  const [username, setUsername] = useState(initialUsername ?? "");
  const [limit, setLimit] = useState(500);
  const [timeClass, setTimeClass] = useState<TimeClassFilter>("");
  const [ratedOnly, setRatedOnly] = useState(false);
  const [repertoire, setRepertoire] = useState<OpeningRepertoire | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("white");
  const [selectedOpening, setSelectedOpening] = useState<OpeningRepertoireRow | null>(null);

  const allOpenings = useMemo(
    () =>
      repertoire
        ? [
            ...repertoire.repertoire.white,
            ...repertoire.repertoire.black_vs_e4,
            ...repertoire.repertoire.black_vs_d4,
            ...repertoire.repertoire.black_vs_other,
          ]
        : [],
    [repertoire],
  );

  async function fetchRepertoire() {
    if (!username.trim()) return;
    const result = await onFetchRepertoire(username.trim(), { limit, time_class: timeClass, rated_only: ratedOnly });
    setRepertoire(result);
    setSelectedOpening(result?.summary.strongest_opening ?? result?.repertoire.white[0] ?? null);
    setActiveTab("white");
  }

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader title="Opening Repertoire" eyebrow="Opening-specific performance">
          See which openings you actually play, how often you play them, and how well they perform.
        </CardHeader>
        <div className="grid gap-3 px-5 pb-5 lg:grid-cols-[1fr_120px_150px_auto_auto] lg:items-center">
          <input
            className="h-11 rounded-md bg-slate-950/80 px-3 text-app-text outline-none ring-1 ring-app-border transition placeholder:text-slate-600 focus:ring-2 focus:ring-app-accent/70"
            value={username}
            placeholder="Chess.com username"
            onChange={(event) => setUsername(event.target.value)}
          />
          <input
            className="h-11 rounded-md bg-slate-950/80 px-3 text-app-text outline-none ring-1 ring-app-border focus:ring-2 focus:ring-app-accent/70"
            type="number"
            min={20}
            max={500}
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          />
          <select
            className="h-11 rounded-md bg-slate-950/80 px-3 text-app-text outline-none ring-1 ring-app-border focus:ring-2 focus:ring-app-accent/70"
            value={timeClass}
            onChange={(event) => setTimeClass(event.target.value as TimeClassFilter)}
          >
            <option value="">All time controls</option>
            <option value="rapid">Rapid</option>
            <option value="blitz">Blitz</option>
            <option value="bullet">Bullet</option>
          </select>
          <label className="flex h-11 items-center gap-2 rounded-md bg-slate-950/80 px-3 text-sm text-app-muted ring-1 ring-app-border">
            <input type="checkbox" className="accent-app-accent" checked={ratedOnly} onChange={(event) => setRatedOnly(event.target.checked)} />
            Rated only
          </label>
          <Button variant="primary" disabled={!username.trim() || loading} onClick={fetchRepertoire}>
            {loading ? "Loading..." : "Build Repertoire"}
          </Button>
        </div>
      </Card>

      {repertoire && (
        <>
          <section className="grid gap-3 md:grid-cols-4">
            <SummaryCard label="Total Games" value={String(repertoire.summary.total_games)} />
            <SummaryCard label="Openings Tracked" value={String(repertoire.summary.openings_tracked)} />
            <SummaryCard label="Strongest Opening" value={repertoire.summary.strongest_opening?.opening_name ?? "-"} detail={fmt(repertoire.summary.strongest_opening?.win_rate, "%")} />
            <SummaryCard label="Weakest Opening" value={repertoire.summary.weakest_opening?.opening_name ?? "-"} detail={fmt(repertoire.summary.weakest_opening?.win_rate, "%")} />
          </section>

          <RecommendationsPanel repertoire={repertoire} />

          <div className="flex flex-wrap gap-2">
            {(["white", "black_vs_e4", "black_vs_d4", "black_vs_other", "trends"] as const).map((tab) => (
              <Button key={tab} variant={activeTab === tab ? "primary" : "secondary"} size="sm" onClick={() => setActiveTab(tab)}>
                {TAB_LABELS[tab]}
              </Button>
            ))}
          </div>

          {activeTab !== "trends" ? (
            <RepertoireTab
              title={TAB_LABELS[activeTab]}
              rows={repertoire.repertoire[activeTab]}
              selectedId={selectedOpening?.id ?? null}
              onSelect={setSelectedOpening}
            />
          ) : (
            <TrendsTab repertoire={repertoire} />
          )}

          <div className="grid gap-5 xl:grid-cols-[1fr_0.8fr]">
            <OpeningExplorer opening={selectedOpening} />
            <CompareOpenings rows={allOpenings} />
          </div>
        </>
      )}
    </div>
  );
}

function SummaryCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <Card className="p-4">
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-app-muted">{label}</p>
      <p className="mt-2 truncate font-mono text-2xl font-black text-app-text">{value}</p>
      {detail && <p className="mt-1 text-sm text-app-muted">{detail}</p>}
    </Card>
  );
}

function RecommendationsPanel({ repertoire }: { repertoire: OpeningRepertoire }) {
  const recommendations = repertoire.recommendations;
  return (
    <Card className="p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-app-muted">Recommendations</p>
          <h2 className="mt-1 text-base font-semibold text-app-text">Opening recommendations</h2>
        </div>
        <Badge tone={recommendations.enough_data ? "green" : "yellow"}>
          {recommendations.enough_data ? "Enough data" : "More games needed"}
        </Badge>
      </div>
      {recommendations.enough_data ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <RecommendationList title="Continue Playing" rows={recommendations.continue_playing} tone="green" />
          <RecommendationList title="Needs Improvement" rows={recommendations.needs_improvement} tone="red" />
          <RecommendationList title="Consider Reviewing" rows={recommendations.consider_reviewing} tone="blue" />
        </div>
      ) : (
        <p className="mt-4 text-sm text-app-muted">
          Recommendations appear after at least two openings have 10 or more games in the selected sample.
        </p>
      )}
    </Card>
  );
}

function RecommendationList({ title, rows, tone }: { title: string; rows: OpeningRepertoireRow[]; tone: "green" | "red" | "blue" }) {
  return (
    <div className="rounded-md bg-slate-950/60 p-4 ring-1 ring-app-border">
      <h3 className="text-sm font-semibold text-app-text">{title}</h3>
      <div className="mt-3 grid gap-2">
        {rows.map((row) => (
          <div key={`${title}-${row.id}`} className="flex items-start justify-between gap-3 text-sm">
            <div className="min-w-0">
              <p className="truncate font-semibold text-slate-200">{row.opening_name}</p>
              <p className="text-xs text-app-muted">{row.games} games</p>
            </div>
            <Badge tone={tone}>{`${fmt(row.win_rate, "%")} WR`}</Badge>
          </div>
        ))}
      </div>
    </div>
  );
}

function RepertoireTab({
  title,
  rows,
  selectedId,
  onSelect,
}: {
  title: string;
  rows: OpeningRepertoireRow[];
  selectedId: string | null;
  onSelect: (row: OpeningRepertoireRow) => void;
}) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
      <OpeningTable title={title} rows={rows} selectedId={selectedId} onSelect={onSelect} />
      <div className="grid gap-5">
        <ChartCard title="Opening frequency">
          <OpeningBar data={rows.slice(0, 10)} dataKey="games" />
        </ChartCard>
        <ChartCard title="Win rate by opening">
          <OpeningBar data={rows.slice(0, 10)} dataKey="win_rate" />
        </ChartCard>
      </div>
    </div>
  );
}

function OpeningTable({
  title,
  rows,
  selectedId,
  onSelect,
}: {
  title: string;
  rows: OpeningRepertoireRow[];
  selectedId: string | null;
  onSelect: (row: OpeningRepertoireRow) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader title={title} eyebrow="Repertoire table">
        Click an opening to inspect recent games, responses, and examples.
      </CardHeader>
      <div className="overflow-x-auto px-5 pb-5">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="text-[11px] uppercase tracking-[0.12em] text-app-muted">
            <tr className="border-b border-app-border">
              <th className="py-2 pr-3">Opening</th>
              <th className="px-3 py-2">Games</th>
              <th className="px-3 py-2">Frequency</th>
              <th className="px-3 py-2">Win Rate</th>
              <th className="px-3 py-2">Accuracy</th>
              <th className="px-3 py-2">CP Loss</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.id}
                className={`cursor-pointer border-b border-app-border/50 transition hover:bg-app-panelSecondary/70 ${
                  selectedId === row.id ? "bg-app-accent/15" : ""
                }`}
                onClick={() => onSelect(row)}
              >
                <td className="max-w-[320px] py-3 pr-3">
                  <p className="truncate font-semibold text-app-text">{row.opening_name}</p>
                  <p className="text-xs text-app-muted">{row.eco}</p>
                </td>
                <td className="px-3 py-3 font-mono">{row.games}</td>
                <td className="px-3 py-3 font-mono">{fmt(row.frequency, "%")}</td>
                <td className="px-3 py-3 font-mono">{fmt(row.win_rate, "%")}</td>
                <td className="px-3 py-3 font-mono">{fmt(row.avg_accuracy)}</td>
                <td className="px-3 py-3 font-mono">{fmt(row.avg_cp_loss, " cp")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p className="py-6 text-sm text-app-muted">No openings in this category for the selected filters.</p>}
      </div>
    </Card>
  );
}

function OpeningBar({ data, dataKey }: { data: OpeningRepertoireRow[]; dataKey: keyof OpeningRepertoireRow }) {
  return (
    <ResponsiveContainer width="100%" height={270}>
      <BarChart data={data.map((row) => ({ ...row, label: shortName(row.opening_name) }))} margin={{ left: -20, right: 8, top: 8, bottom: 48 }}>
        <CartesianGrid stroke="#263244" strokeDasharray="3 6" vertical={false} />
        <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 10 }} angle={-25} textAnchor="end" interval={0} height={72} />
        <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={{ background: "#111827", border: "1px solid #263244", borderRadius: 8 }} />
        <Bar dataKey={dataKey as string} fill="#3b82f6" radius={[5, 5, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function TrendsTab({ repertoire }: { repertoire: OpeningRepertoire }) {
  const [windowKey, setWindowKey] = useState<TrendWindowKey>("last_90");
  const window = repertoire.trends.windows[windowKey];
  const topOpenings = window.openings.slice(0, 10);

  return (
    <div className="grid gap-5">
      <Card className="p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-app-muted">Trend window</p>
            <h2 className="mt-1 text-base font-semibold text-app-text">{window.games} games in sample</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {(["last_30", "last_90", "last_180", "all"] as const).map((key) => (
              <Button key={key} variant={windowKey === key ? "primary" : "secondary"} size="sm" onClick={() => setWindowKey(key)}>
                {key === "all" ? "All games" : key.replace("_", " ")}
              </Button>
            ))}
          </div>
        </div>
      </Card>
      <div className="grid gap-5 xl:grid-cols-3">
        <ChartCard title="Opening usage">
          <OpeningBar data={topOpenings} dataKey="games" />
        </ChartCard>
        <ChartCard title="Accuracy by opening">
          <OpeningBar data={topOpenings} dataKey="avg_accuracy" />
        </ChartCard>
        <ChartCard title="Win rate by opening">
          <OpeningBar data={topOpenings} dataKey="win_rate" />
        </ChartCard>
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <ChartCard title="Accuracy over games">
          <TrendLine data={repertoire.trends.points} dataKey="accuracy" stroke="#22c55e" />
        </ChartCard>
        <ChartCard title="Result rate over games">
          <TrendLine data={repertoire.trends.points} dataKey="win_rate" stroke="#3b82f6" />
        </ChartCard>
      </div>
    </div>
  );
}

function TrendLine({ data, dataKey, stroke }: { data: OpeningTrendPoint[]; dataKey: "accuracy" | "win_rate"; stroke: string }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ left: -20, right: 8, top: 8, bottom: 8 }}>
        <CartesianGrid stroke="#263244" strokeDasharray="3 6" vertical={false} />
        <XAxis dataKey="game_index" tick={{ fill: "#94a3b8", fontSize: 10 }} minTickGap={24} />
        <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={{ background: "#111827", border: "1px solid #263244", borderRadius: 8 }} />
        <Line type="monotone" dataKey={dataKey} stroke={stroke} strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function OpeningExplorer({ opening }: { opening: OpeningRepertoireRow | null }) {
  if (!opening) {
    return (
      <Card className="p-5">
        <h2 className="text-base font-semibold">Opening Explorer</h2>
        <p className="mt-2 text-sm text-app-muted">Select an opening from a table to inspect it.</p>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader title="Opening Explorer" eyebrow="Selected opening">
        {opening.eco} - {opening.opening_name}
      </CardHeader>
      <div className="grid gap-5 px-5 pb-5">
        <div className="grid gap-3 sm:grid-cols-4">
          <MiniMetric label="Games" value={String(opening.games)} />
          <MiniMetric label="Win Rate" value={fmt(opening.win_rate, "%")} />
          <MiniMetric label="Accuracy" value={fmt(opening.avg_accuracy)} />
          <MiniMetric label="Avg Length" value={fmt(opening.avg_game_length)} />
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <StatList title="Most Common Opponent Responses" rows={opening.common_opponent_responses.map((row) => `${row.move} - ${row.games} games (${row.frequency}%)`)} />
          <StatList title="Typical Results" rows={opening.typical_results.map((row) => `${row.result} - ${row.games} games (${row.frequency}%)`)} />
          <GameList title="Recent Games" rows={opening.recent_games} />
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <GameList title="Best Example Games" rows={opening.best_example_games} />
          <GameList title="Worst Example Games" rows={opening.worst_example_games} />
        </div>
      </div>
    </Card>
  );
}

function CompareOpenings({ rows }: { rows: OpeningRepertoireRow[] }) {
  const [openingA, setOpeningA] = useState("");
  const [openingB, setOpeningB] = useState("");
  const first = rows.find((row) => row.id === openingA) ?? rows[0];
  const second = rows.find((row) => row.id === openingB) ?? rows[1];

  return (
    <Card className="p-5">
      <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-app-muted">Bonus</p>
      <h2 className="mt-1 text-base font-semibold text-app-text">Compare Openings</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <OpeningSelect rows={rows} value={first?.id ?? ""} onChange={setOpeningA} />
        <OpeningSelect rows={rows} value={second?.id ?? ""} onChange={setOpeningB} />
      </div>
      {first && second ? (
        <div className="mt-5 grid gap-3">
          <CompareRow label="Games" a={String(first.games)} b={String(second.games)} />
          <CompareRow label="Win Rate" a={fmt(first.win_rate, "%")} b={fmt(second.win_rate, "%")} />
          <CompareRow label="Accuracy" a={fmt(first.avg_accuracy)} b={fmt(second.avg_accuracy)} />
          <CompareRow label="Average CP Loss" a={fmt(first.avg_cp_loss, " cp")} b={fmt(second.avg_cp_loss, " cp")} />
        </div>
      ) : (
        <p className="mt-4 text-sm text-app-muted">At least two openings are needed for comparison.</p>
      )}
    </Card>
  );
}

function OpeningSelect({ rows, value, onChange }: { rows: OpeningRepertoireRow[]; value: string; onChange: (value: string) => void }) {
  return (
    <select
      className="h-11 min-w-0 rounded-md bg-slate-950/80 px-3 text-app-text outline-none ring-1 ring-app-border focus:ring-2 focus:ring-app-accent/70"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    >
      {rows.map((row) => (
        <option key={row.id} value={row.id}>
          {row.opening_name}
        </option>
      ))}
    </select>
  );
}

function CompareRow({ label, a, b }: { label: string; a: string; b: string }) {
  return (
    <div className="grid grid-cols-[1fr_0.8fr_0.8fr] items-center gap-3 rounded-md bg-slate-950/70 px-3 py-2 text-sm ring-1 ring-app-border">
      <span className="text-app-muted">{label}</span>
      <span className="font-mono text-app-text">{a}</span>
      <span className="font-mono text-app-text">{b}</span>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-slate-950/70 p-3 ring-1 ring-app-border">
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-app-muted">{label}</p>
      <p className="mt-2 font-mono text-lg font-black text-app-text">{value}</p>
    </div>
  );
}

function StatList({ title, rows }: { title: string; rows: string[] }) {
  return (
    <div className="rounded-md bg-slate-950/60 p-4 ring-1 ring-app-border">
      <h3 className="text-sm font-semibold text-app-text">{title}</h3>
      <div className="mt-3 grid gap-2 text-sm text-slate-300">
        {rows.length ? rows.map((row) => <p key={row}>{row}</p>) : <p className="text-app-muted">No data yet.</p>}
      </div>
    </div>
  );
}

function GameList({ title, rows }: { title: string; rows: OpeningGameExample[] }) {
  return (
    <div className="rounded-md bg-slate-950/60 p-4 ring-1 ring-app-border">
      <h3 className="text-sm font-semibold text-app-text">{title}</h3>
      <div className="mt-3 grid gap-2">
        {rows.length ? (
          rows.map((row, index) => (
            <a
              key={`${title}-${row.url ?? index}`}
              className="grid grid-cols-[1fr_auto] gap-3 rounded bg-app-panelSecondary/70 px-3 py-2 text-sm transition hover:bg-slate-700"
              href={row.url ?? undefined}
              target="_blank"
              rel="noreferrer"
            >
              <span className="min-w-0 truncate text-slate-200">
                {row.date ?? "Unknown date"} vs {row.opponent}
              </span>
              <span className="font-mono text-app-muted">{row.result}</span>
            </a>
          ))
        ) : (
          <p className="text-sm text-app-muted">No games available.</p>
        )}
      </div>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="p-5">
      <h3 className="mb-4 text-base font-semibold">{title}</h3>
      {children}
    </Card>
  );
}
