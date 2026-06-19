import type { OpeningInsight, PlayerInsights, TimeClassFilter } from "../types";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { Area, AreaChart, ResponsiveContainer as RC, Tooltip as TT, YAxis } from "recharts";
import { BarChart3, BookOpen, Crosshair, Filter, Lightbulb, Search, Target, ThumbsUp, TrendingUp, Trophy } from "lucide-react";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";
import { Delta } from "./ui/Delta";
import { Sparkline } from "./ui/Sparkline";
import { StatCard } from "./ui/StatCard";
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

const PIE_COLORS = ["#c8a15a", "#5cb585", "#34c9bb", "#dc8a45", "#dd5b52", "#d6b24a", "#9b9ca6", "#7c8aa5"];
const TOOLTIP_STYLE = {
  background: "#191a1e",
  border: "1px solid #34363d",
  borderRadius: 10,
  color: "#f3f3f5",
  boxShadow: "0 16px 48px -16px rgba(0,0,0,0.7)",
};

const inputBase =
  "h-11 w-full rounded-lg border border-app-border bg-app-bgInset px-3 text-sm text-app-text outline-none transition placeholder:text-app-faint focus-visible:border-app-accentLine focus-visible:ring-2 focus-visible:ring-app-accent/40";

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
        <div className="grid gap-3 lg:grid-cols-[1fr_120px_150px_auto_auto] lg:items-center">
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
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <div className="grid h-11 w-11 place-items-center rounded-full bg-app-panelSecondary text-app-muted">
          <BarChart3 className="h-5 w-5" />
        </div>
        <p className="text-sm text-app-muted">
          {loading ? "Reading public games and building your insights..." : "Enter a Chess.com username, then refresh to build player insights."}
        </p>
      </div>
    </Card>
  );
}

function InsightsReport({ insights }: { insights: PlayerInsights }) {
  const openings = topOpenings(insights);
  const hasAccuracy = insights.summary.games_with_accuracy > 0;
  const s = insights.summary;
  const perf = insights.performance;

  const accuracyDelta =
    perf.last_30.avg_accuracy != null && perf.last_90.avg_accuracy != null
      ? perf.last_30.avg_accuracy - perf.last_90.avg_accuracy
      : null;
  const winRateDelta = perf.last_30.win_rate - perf.last_90.win_rate;
  const ratingSeries = perf.rating_points.map((p) => p.rating);
  const currentRating = ratingSeries.length ? ratingSeries[ratingSeries.length - 1] : null;
  const ratingDelta = ratingSeries.length > 1 ? currentRating! - ratingSeries[0] : null;
  const accuracySeries = perf.trend_points.map((p) => p.accuracy).filter((n) => Number.isFinite(n));

  return (
    <div className="grid gap-5">
      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Win rate"
          value={fmt(s.win_rate)}
          unit="%"
          icon={Trophy}
          delta={winRateDelta}
          deltaSuffix="%"
          caption={`W ${fmt(s.white_win_rate)}% · B ${fmt(s.black_win_rate)}%`}
        />
        <StatCard
          label="Accuracy"
          value={hasAccuracy ? fmt(s.average_accuracy) : "—"}
          unit={hasAccuracy ? "%" : undefined}
          icon={Target}
          delta={accuracyDelta}
          deltaSuffix="%"
          caption={hasAccuracy ? `${s.games_with_accuracy} analysed` : "review a game"}
        />
        <StatCard
          label="Rating"
          value={currentRating ?? "—"}
          icon={TrendingUp}
          delta={ratingDelta}
          caption={currentRating ? "latest" : "no data"}
          visual={ratingSeries.length > 1 ? <Sparkline data={ratingSeries} width={72} height={30} /> : undefined}
        />
        <StatCard label="Avg. cp loss" value={fmt(s.average_cp_loss)} icon={Crosshair} caption="lower is better" />
      </div>

      {/* Performance trend */}
      {accuracySeries.length > 1 && (
        <Card>
          <div className="flex items-end justify-between pb-3">
            <CardHeader title="Accuracy trend" eyebrow="Recent form" />
            <div className="flex items-center gap-2 pb-4 text-xs text-app-muted">
              <Delta value={accuracyDelta} suffix="%" />
              <span>last 30 vs 90 days</span>
            </div>
          </div>
          <div className="h-44 w-full">
            <RC width="100%" height="100%">
              <AreaChart data={accuracySeries.map((value, i) => ({ i, value }))} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="insightTrend" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#c8a15a" stopOpacity={0.26} />
                    <stop offset="100%" stopColor="#c8a15a" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <YAxis hide domain={["dataMin - 3", "dataMax + 3"]} />
                <TT contentStyle={TOOLTIP_STYLE} labelFormatter={() => ""} formatter={(v: number) => [`${v.toFixed(1)}%`, "Accuracy"]} />
                <Area type="monotone" dataKey="value" stroke="#c8a15a" strokeWidth={2} fill="url(#insightTrend)" dot={false} />
              </AreaChart>
            </RC>
          </div>
        </Card>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Most common openings" eyebrow="Repertoire" />
          <InsightList rows={openings.map((row) => `${row.opening_name} - ${row.games} games`)} />
        </Card>

        <Card>
          <CardHeader title="Likely trouble spots" eyebrow="Estimated from results">
            Rough patterns from public game data, not a full engine diagnosis.
          </CardHeader>
          <MistakePie data={insights.mistakes.by_phase} />
        </Card>
      </div>

      <ProfileCard insights={insights} />
    </div>
  );
}

function ProfileCard({ insights }: { insights: PlayerInsights }) {
  const { profile } = insights;
  const hasContent =
    profile.style || profile.strengths.length || profile.weaknesses.length || profile.recommendations.length;
  if (!hasContent) return null;

  return (
    <Card>
      <CardHeader title={profile.style ? `Your style: ${profile.style}` : "Coach's read"} eyebrow="Profile">
        {profile.summary || "A coach-style read of your habits and what to work on next."}
      </CardHeader>
      <div className="grid gap-5 sm:grid-cols-3">
        <ProfileColumn icon={ThumbsUp} title="Strengths" tone="text-app-good" items={profile.strengths} />
        <ProfileColumn icon={Crosshair} title="Weaknesses" tone="text-app-mistake" items={profile.weaknesses} />
        <ProfileColumn icon={Lightbulb} title="Work on next" tone="text-app-accent" items={profile.recommendations} />
      </div>
    </Card>
  );
}

function ProfileColumn({
  icon: Icon,
  title,
  tone,
  items,
}: {
  icon: typeof BarChart3;
  title: string;
  tone: string;
  items: string[];
}) {
  return (
    <div className="rounded-xl border border-app-border bg-app-bgInset/60 p-4">
      <div className={`flex items-center gap-2 text-sm font-semibold ${tone}`}>
        <Icon className="h-4 w-4" />
        {title}
      </div>
      {items.length ? (
        <ul className="mt-3 space-y-2">
          {items.slice(0, 4).map((item, i) => (
            <li key={i} className="flex gap-2 text-sm leading-relaxed text-app-muted">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-current opacity-50" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-app-subtle">Not enough data yet.</p>
      )}
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
            labelStyle={{ color: "#ededf0" }}
            itemStyle={{ color: "#ededf0" }}
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
            className="grid grid-cols-[12px_1fr_auto] items-center gap-3 border-b border-app-border py-2 text-sm last:border-b-0"
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

function InsightList({ rows }: { rows: string[] }) {
  if (!rows.length) {
    return <p className="text-sm text-app-muted">No openings to show yet.</p>;
  }
  return (
    <ol className="overflow-hidden rounded-lg divide-y divide-app-border">
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
