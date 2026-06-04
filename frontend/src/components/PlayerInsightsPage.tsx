import type { OpeningInsight, PlayerInsights, TimeClassFilter } from "../types";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";
import { openingFamily } from "../utils/openingFamilies";

interface PlayerInsightsPageProps {
  loading: boolean;
  insights: PlayerInsights | null;
  username: string;
  onUsernameChange: (username: string) => void;
  limit: number;
  onLimitChange: (limit: number) => void;
  timeClass: TimeClassFilter;
  onTimeClassChange: (timeClass: TimeClassFilter) => void;
  ratedOnly: boolean;
  onRatedOnlyChange: (ratedOnly: boolean) => void;
  onFetchInsights: (
    username: string,
    params: { limit: number; time_class: TimeClassFilter; rated_only: boolean },
  ) => Promise<PlayerInsights | null>;
}

function fmt(value: number | null | undefined, suffix = "") {
  return value === null || value === undefined ? "-" : `${value.toFixed(1)}${suffix}`;
}

function topOpenings(insights: PlayerInsights) {
  const groups = new Map<string, OpeningInsight>();

  for (const row of [...insights.openings.as_white, ...insights.openings.as_black]) {
    const family = openingFamily(row.opening_family, row.opening_name);
    const existing = groups.get(family);
    if (existing) {
      existing.games += row.games;
      existing.variations = [...existing.variations, ...row.variations];
    } else {
      groups.set(family, { ...row, opening_name: family, opening_family: family, variation: null });
    }
  }

  return [...groups.values()]
    .sort((a, b) => b.games - a.games)
    .slice(0, 3);
}

const PIE_COLORS = ["#007acc", "#dcdcaa", "#ce9178", "#f14c4c", "#767676", "#89d185", "#b180d7", "#4ec9b0"];
const TOOLTIP_STYLE = { background: "#1f1f1f", border: "none", borderRadius: 6, color: "#d4d4d4" };

export function PlayerInsightsPage({
  loading,
  insights,
  username,
  onUsernameChange,
  limit,
  onLimitChange,
  timeClass,
  onTimeClassChange,
  ratedOnly,
  onRatedOnlyChange,
  onFetchInsights,
}: PlayerInsightsPageProps) {
  async function fetchInsights() {
    if (!username.trim()) return;
    await onFetchInsights(username.trim(), { limit, time_class: timeClass, rated_only: ratedOnly });
  }

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader title="Player Insights" eyebrow="Chess.com history">
          A quick coach-style readout of your recent habits and study priorities.
        </CardHeader>
        <div className="grid gap-3 px-5 pb-5 lg:grid-cols-[1fr_120px_150px_auto_auto] lg:items-center">
          <input
            className="h-11 bg-app-panelSecondary px-3 text-app-text outline-none transition placeholder:text-app-muted focus:bg-[#3c3c3c]"
            value={username}
            placeholder="Chess.com username"
            onChange={(event) => onUsernameChange(event.target.value)}
          />
          <input
            className="h-11 bg-app-panelSecondary px-3 text-app-text outline-none transition focus:bg-[#3c3c3c]"
            type="number"
            min={20}
            max={300}
            value={limit}
            onChange={(event) => onLimitChange(Number(event.target.value))}
          />
          <select
            className="h-11 bg-app-panelSecondary px-3 text-app-text outline-none transition focus:bg-[#3c3c3c]"
            value={timeClass}
            onChange={(event) => onTimeClassChange(event.target.value as TimeClassFilter)}
          >
            <option value="">All time controls</option>
            <option value="rapid">Rapid</option>
            <option value="blitz">Blitz</option>
            <option value="bullet">Bullet</option>
          </select>
          <label className="flex h-11 items-center gap-2 bg-app-panelSecondary px-3 text-sm text-app-muted">
            <input type="checkbox" className="accent-app-accent" checked={ratedOnly} onChange={(event) => onRatedOnlyChange(event.target.checked)} />
            Rated only
          </label>
          <Button variant="primary" disabled={!username.trim() || loading} onClick={fetchInsights}>
            {loading ? "Loading..." : "Refresh Insights"}
          </Button>
        </div>
      </Card>

      {insights ? <InsightsReport insights={insights} /> : <EmptyState loading={loading} />}
    </div>
  );
}

function EmptyState({ loading }: { loading: boolean }) {
  return (
    <Card className="p-5">
      <p className="text-sm text-app-muted">
        {loading ? "Building your insights..." : "Enter a Chess.com username to build player insights."}
      </p>
    </Card>
  );
}

function InsightsReport({ insights }: { insights: PlayerInsights }) {
  const openings = topOpenings(insights);

  return (
    <section className="bg-app-panel">
      <div className="px-5 py-6">
        <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">Summary</p>
        <h2 className="mt-1 text-2xl font-medium text-app-text">Player Insights</h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <Metric label="Games" value={String(insights.summary.games_analyzed)} />
          <Metric label="Win rate" value={fmt(insights.summary.win_rate, "%")} />
          <Metric label="Accuracy" value={fmt(insights.summary.average_accuracy, "%")} />
        </div>
      </div>

      <div className="px-5 py-5">
        <InsightList title="Most Common Openings" rows={openings.map((row) => `${row.opening_name} - ${row.games} games`)} />
      </div>

      <div className="px-5 py-6">
        <MistakePie title="Where Mistakes Happen" data={insights.mistakes.by_phase} />
      </div>
    </section>
  );
}

function MistakePie({ title, data }: { title: string; data: Array<{ category: string; count: number; percentage: number }> }) {
  const filtered = data.filter((row) => row.count > 0);

  return (
    <div>
      <h3 className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">{title}</h3>
      {filtered.length ? (
        <div className="mt-4 grid gap-4 md:grid-cols-[220px_1fr] md:items-center">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={filtered} dataKey="count" nameKey="category" innerRadius={54} outerRadius={88} paddingAngle={2}>
                {filtered.map((row, index) => (
                  <Cell key={row.category} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                labelStyle={{ color: "#d4d4d4" }}
                itemStyle={{ color: "#d4d4d4" }}
                formatter={(_value, name, props) => {
                  const percentage = Number(props.payload?.percentage ?? 0);
                  return [`${Math.round(percentage)}%`, name];
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="grid gap-2">
            {filtered.map((row, index) => (
              <div key={row.category} className="grid grid-cols-[12px_1fr_auto] items-center gap-2 text-sm">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: PIE_COLORS[index % PIE_COLORS.length] }} />
                <span className="text-app-text">{row.category}</span>
                <span className="font-mono text-app-muted">{row.count}</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="mt-4 text-sm text-app-muted">No mistake data available yet.</p>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-app-muted">{label}</p>
      <p className="mt-1 font-mono text-xl font-medium text-app-text">{value}</p>
    </div>
  );
}

function InsightList({ title, rows }: { title: string; rows: string[] }) {
  return (
    <div className="min-w-0">
      <h3 className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">{title}</h3>
      <ol className="mt-4 grid gap-3">
        {rows.slice(0, 5).map((row, index) => (
          <li key={`${title}-${row}`} className="grid grid-cols-[24px_1fr] gap-3 pb-2 text-sm">
            <span className="font-mono text-app-muted">{index + 1}.</span>
            <span className="min-w-0 text-app-text">{row}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
