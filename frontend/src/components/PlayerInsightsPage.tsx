import type { OpeningInsight, PlayerInsights, TimeClassFilter } from "../types";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { BarChart3, BookOpen, Filter, Search, Target, Trophy } from "lucide-react";
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

const PIE_COLORS = ["#6366f1", "#fbbf24", "#fb923c", "#f43f5e", "#9aa0aa", "#34d399", "#a78bfa", "#22d3ee"];
const TOOLTIP_STYLE = {
  background: "#16181d",
  border: "1px solid #262a31",
  borderRadius: 8,
  color: "#e6e8ec",
};

const inputBase =
  "h-11 w-full rounded-lg border border-app-border bg-app-panelSecondary px-3 text-sm text-app-text outline-none transition placeholder:text-app-muted focus-visible:border-app-accent focus-visible:ring-2 focus-visible:ring-app-accent/50";

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
    <div className="grid animate-fade-in gap-5">
      <Card>
        <CardHeader title="Player Insights" eyebrow="Chess.com history">
          A quick coach-style readout of your recent habits and study priorities.
        </CardHeader>
        <div className="grid gap-3 px-5 pb-5 pt-4 lg:grid-cols-[1fr_120px_150px_auto_auto] lg:items-center">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-app-faint" />
            <input
              className={`${inputBase} pl-9`}
              value={username}
              placeholder="Chess.com username"
              onChange={(event) => onUsernameChange(event.target.value)}
            />
          </div>
          <input
            className={`${inputBase} font-mono`}
            type="number"
            min={20}
            max={300}
            value={limit}
            onChange={(event) => onLimitChange(Number(event.target.value))}
          />
          <select
            className={inputBase}
            value={timeClass}
            onChange={(event) => onTimeClassChange(event.target.value as TimeClassFilter)}
          >
            <option value="">All time controls</option>
            <option value="rapid">Rapid</option>
            <option value="blitz">Blitz</option>
            <option value="bullet">Bullet</option>
          </select>
          <label className="flex h-11 cursor-pointer items-center gap-2 rounded-lg border border-app-border bg-app-panelSecondary px-3 text-sm text-app-muted transition hover:bg-app-panelHover">
            <input type="checkbox" className="h-4 w-4 accent-app-accent" checked={ratedOnly} onChange={(event) => onRatedOnlyChange(event.target.checked)} />
            Rated only
          </label>
          <Button variant="primary" disabled={!username.trim() || loading} onClick={fetchInsights}>
            <Filter className="h-4 w-4" />
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
    <Card>
      <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
        <div className="grid h-11 w-11 place-items-center rounded-full bg-app-accentSoft text-app-accent">
          <BarChart3 className="h-5 w-5" />
        </div>
        <p className="text-sm text-app-muted">
          {loading ? "Building your insights..." : "Enter a Chess.com username to build player insights."}
        </p>
      </div>
    </Card>
  );
}

function InsightsReport({ insights }: { insights: PlayerInsights }) {
  const openings = topOpenings(insights);

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader title="Summary" eyebrow="Overview" />
        <div className="grid gap-3 px-5 py-5 sm:grid-cols-3">
          <Metric label="Games" value={String(insights.summary.games_analyzed)} icon={BarChart3} />
          <Metric label="Win rate" value={fmt(insights.summary.win_rate, "%")} icon={Trophy} tone="good" />
          <Metric
            label="Accuracy"
            value={fmt(insights.summary.average_accuracy, "%")}
            icon={Target}
            tone="accent"
            sub={
              insights.summary.games_with_accuracy > 0
                ? `Chess.com review · ${insights.summary.games_with_accuracy} of ${insights.summary.games_analyzed} games`
                : "No Chess.com-analysed games"
            }
          />
        </div>
      </Card>

      <Card>
        <CardHeader title="Most Common Openings" eyebrow="Repertoire" />
        <div className="px-5 py-5">
          <InsightList rows={openings.map((row) => `${row.opening_name} - ${row.games} games`)} />
        </div>
      </Card>

      <Card>
        <CardHeader title="Where Mistakes Happen" eyebrow="Error analysis" />
        <div className="px-5 py-5">
          <MistakePie data={insights.mistakes.by_phase} />
        </div>
      </Card>
    </div>
  );
}

function MistakePie({ data }: { data: Array<{ category: string; count: number; percentage: number }> }) {
  const filtered = data.filter((row) => row.count > 0);

  if (!filtered.length) {
    return <p className="text-sm text-app-muted">No mistake data available yet.</p>;
  }

  return (
    <div className="grid gap-4 md:grid-cols-[220px_1fr] md:items-center">
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie data={filtered} dataKey="count" nameKey="category" innerRadius={54} outerRadius={88} paddingAngle={2} stroke="none">
            {filtered.map((row, index) => (
              <Cell key={row.category} fill={PIE_COLORS[index % PIE_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelStyle={{ color: "#e6e8ec" }}
            itemStyle={{ color: "#e6e8ec" }}
            formatter={(_value, name, props) => {
              const percentage = Number(props.payload?.percentage ?? 0);
              return [`${Math.round(percentage)}%`, name];
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="grid gap-2">
        {filtered.map((row, index) => (
          <div
            key={row.category}
            className="grid grid-cols-[12px_1fr_auto] items-center gap-3 rounded-lg border border-app-border bg-app-panelSecondary/40 px-3 py-2 text-sm"
          >
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: PIE_COLORS[index % PIE_COLORS.length] }} />
            <span className="text-app-text">{row.category}</span>
            <span className="font-mono text-app-muted">{row.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
  icon: Icon,
  tone = "default",
  sub,
}: {
  label: string;
  value: string;
  icon: typeof BarChart3;
  tone?: "default" | "good" | "accent";
  sub?: string;
}) {
  const toneClass = tone === "good" ? "text-app-good" : tone === "accent" ? "text-app-accent" : "text-app-faint";
  return (
    <div className="rounded-lg border border-app-border bg-app-panelSecondary/40 p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-app-muted">{label}</p>
        <Icon className={`h-4 w-4 ${toneClass}`} />
      </div>
      <p className="mt-2 font-mono text-2xl font-semibold text-app-text">{value}</p>
      {sub && <p className="mt-1 text-[11px] text-app-muted">{sub}</p>}
    </div>
  );
}

function InsightList({ rows }: { rows: string[] }) {
  if (!rows.length) {
    return <p className="text-sm text-app-muted">No openings to show yet.</p>;
  }
  return (
    <ol className="overflow-hidden rounded-lg border border-app-border divide-y divide-app-border">
      {rows.slice(0, 5).map((row, index) => (
        <li
          key={`opening-${row}`}
          className="flex items-center gap-3 px-4 py-3 text-sm transition hover:bg-app-panelSecondary/50"
        >
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-app-accentSoft font-mono text-xs text-app-accent">
            {index + 1}
          </span>
          <BookOpen className="h-4 w-4 shrink-0 text-app-faint" />
          <span className="min-w-0 truncate text-app-text">{row}</span>
        </li>
      ))}
    </ol>
  );
}
