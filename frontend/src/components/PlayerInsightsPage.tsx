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

function trendDirection(current: number | null | undefined, previous: number | null | undefined, lowerIsBetter = false) {
  if (current === null || current === undefined || previous === null || previous === undefined) {
    return { arrow: "->", label: "Not enough data" };
  }
  const delta = current - previous;
  if (Math.abs(delta) < 1) return { arrow: "->", label: "Stable" };
  const improving = lowerIsBetter ? delta < 0 : delta > 0;
  return improving ? { arrow: "^", label: "Improving" } : { arrow: "v", label: "Needs attention" };
}

function topOpenings(insights: PlayerInsights) {
  return [...insights.openings.as_white, ...insights.openings.as_black]
    .sort((a, b) => b.games - a.games)
    .slice(0, 3);
}

const PIE_COLORS = ["#3b82f6", "#eab308", "#f97316", "#ef4444", "#64748b", "#22c55e", "#a855f7", "#14b8a6"];
const TOOLTIP_STYLE = { background: "#111827", border: "1px solid #263244", borderRadius: 6, color: "#f8fafc" };

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
            className="h-11 border-[0.5px] border-app-border bg-app-panel px-3 text-app-text outline-none transition placeholder:text-app-muted focus:border-app-text"
            value={username}
            placeholder="Chess.com username"
            onChange={(event) => onUsernameChange(event.target.value)}
          />
          <input
            className="h-11 border-[0.5px] border-app-border bg-app-panel px-3 text-app-text outline-none focus:border-app-text"
            type="number"
            min={20}
            max={300}
            value={limit}
            onChange={(event) => onLimitChange(Number(event.target.value))}
          />
          <select
            className="h-11 border-[0.5px] border-app-border bg-app-panel px-3 text-app-text outline-none focus:border-app-text"
            value={timeClass}
            onChange={(event) => onTimeClassChange(event.target.value as TimeClassFilter)}
          >
            <option value="">All time controls</option>
            <option value="rapid">Rapid</option>
            <option value="blitz">Blitz</option>
            <option value="bullet">Bullet</option>
          </select>
          <label className="flex h-11 items-center gap-2 border-[0.5px] border-app-border bg-app-panel px-3 text-sm text-app-muted">
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
  const accuracyTrend = trendDirection(insights.performance.last_30.avg_accuracy, insights.performance.last_90.avg_accuracy);
  const blunderTrend = trendDirection(insights.performance.last_30.blunders, insights.performance.last_90.blunders, true);
  const winTrend = trendDirection(insights.performance.last_30.win_rate, insights.performance.last_90.win_rate);
  const recommendations = insights.profile.recommendations.slice(0, 5);

  return (
    <section className="bg-app-panel">
      <div className="grid gap-6 border-b border-app-border px-5 py-5 xl:grid-cols-[1fr_0.9fr]">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">Summary</p>
          <h2 className="mt-1 text-2xl font-medium text-app-text">Player Insights</h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            <Metric label="Games" value={String(insights.summary.games_analyzed)} />
            <Metric label="Win rate" value={fmt(insights.summary.win_rate, "%")} />
            <Metric label="Accuracy" value={fmt(insights.summary.average_accuracy, "%")} />
          </div>
        </div>
        <div className="border-t border-app-border pt-5 xl:border-l xl:border-t-0 xl:pl-6 xl:pt-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">Recent trend</p>
          <div className="mt-4 grid gap-3">
            <TrendLine label="Accuracy" trend={accuracyTrend} />
            <TrendLine label="Blunders" trend={blunderTrend} />
            <TrendLine label="Win rate" trend={winTrend} />
          </div>
        </div>
      </div>

      <div className="grid gap-6 px-5 py-5 xl:grid-cols-3">
        <InsightList title="Most Common Openings" rows={openings.map((row) => `${row.opening_name} - ${row.games} games`)} />
        <InsightList title="Most Common Mistakes" rows={insights.mistakes.top_weaknesses.slice(0, 5).map((row) => `${row.category} - ${row.count}`)} />
        <InsightList title="Recommendations" rows={recommendations.length ? recommendations : fallbackRecommendations(insights)} />
      </div>

      <div className="grid gap-6 border-t border-app-border px-5 py-5 xl:grid-cols-2">
        <MistakePie title="Where Mistakes Happen" data={insights.mistakes.by_phase} />
        <MistakePie title="Mistake Types" data={insights.mistakes.by_type.slice(0, 6)} />
      </div>

      <div className="border-t border-app-border px-5 py-5">
        <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">Coach note</p>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-app-muted">{insights.profile.summary}</p>
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
              <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: "#f8fafc" }} itemStyle={{ color: "#f8fafc" }} />
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

function TrendLine({ label, trend }: { label: string; trend: { arrow: string; label: string } }) {
  return (
    <div className="grid grid-cols-[90px_24px_1fr] items-center gap-2 text-sm">
      <span className="text-app-muted">{label}</span>
      <span className="font-mono text-app-text">{trend.arrow}</span>
      <span className="font-medium text-app-text">{trend.label}</span>
    </div>
  );
}

function InsightList({ title, rows }: { title: string; rows: string[] }) {
  return (
    <div className="min-w-0">
      <h3 className="text-[11px] font-medium uppercase tracking-[0.16em] text-app-muted">{title}</h3>
      <ol className="mt-4 grid gap-3">
        {rows.slice(0, 5).map((row, index) => (
          <li key={`${title}-${row}`} className="grid grid-cols-[24px_1fr] gap-3 border-b border-app-border/70 pb-3 text-sm">
            <span className="font-mono text-app-muted">{index + 1}.</span>
            <span className="min-w-0 text-app-text">{row}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function fallbackRecommendations(insights: PlayerInsights) {
  const weakness = insights.profile.top_weakness;
  const openings = topOpenings(insights).map((row: OpeningInsight) => row.opening_name);
  return [
    weakness ? `Review ${weakness.toLowerCase()}` : "Review tactical misses",
    insights.profile.position_preference ? `Study ${insights.profile.position_preference.toLowerCase()} positions` : "Review model games",
    openings[0] ? `Study ${openings[0]} structures` : "Build a repeatable opening plan",
  ];
}
