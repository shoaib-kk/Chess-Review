import { useState } from "react";
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
import type { OpeningInsight, PlayerInsights, TimeClassFilter } from "../types";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";
import { Badge } from "./ui/Badge";

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

const CHART_GRID = "rgba(0,0,0,0.1)";
const CHART_TEXT = "#6b6b6b";
const CHART_STROKE = "#1a1a1a";
const TOOLTIP_STYLE = { background: "#ffffff", border: "0.5px solid rgba(0,0,0,0.1)", borderRadius: 0, color: "#1a1a1a" };

function fmt(value: number | null | undefined, suffix = "") {
  return value === null || value === undefined ? "-" : `${value.toFixed(1)}${suffix}`;
}

function shortLabel(value: string) {
  return value.length > 22 ? `${value.slice(0, 22)}...` : value;
}

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
  const [activeTab, setActiveTab] = useState<"openings" | "mistakes" | "profile">("openings");

  async function fetchInsights() {
    if (!username.trim()) return;
    await onFetchInsights(username.trim(), { limit, time_class: timeClass, rated_only: ratedOnly });
  }

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader title="Player Insights" eyebrow="Chess.com history">
          High-level opening habits, weaknesses, and recommendations.
        </CardHeader>
        <div className="grid gap-3 px-5 pb-5 lg:grid-cols-[1fr_120px_150px_auto_auto] lg:items-center">
          <input
            className="h-11 border-[0.5px] border-app-border bg-app-panel px-3 text-app-text outline-none transition placeholder:text-[#9b9b9b] focus:border-app-text"
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
            {loading ? "Loading..." : "Generate Insights"}
          </Button>
        </div>
      </Card>

      {insights && (
        <>
          <SummaryRow
            items={[
              { label: "Games Analyzed", value: String(insights.summary.games_analyzed) },
              { label: "Win Rate", value: fmt(insights.summary.win_rate, "%") },
              { label: "Average Accuracy", value: fmt(insights.summary.average_accuracy) },
              { label: "Average CP Loss", value: fmt(insights.summary.average_cp_loss, " cp") },
            ]}
          />

          <div className="flex flex-wrap gap-2">
            {(["openings", "mistakes", "profile"] as const).map((tab) => (
              <Button key={tab} variant={activeTab === tab ? "primary" : "secondary"} size="sm" onClick={() => setActiveTab(tab)}>
                {tab[0].toUpperCase() + tab.slice(1)}
              </Button>
            ))}
          </div>

          {activeTab === "openings" && <OpeningsTab insights={insights} />}
          {activeTab === "mistakes" && <MistakesTab insights={insights} />}
          {activeTab === "profile" && <ProfileTab insights={insights} />}
        </>
      )}
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-4">
      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-app-muted">{label}</p>
      <p className="mt-2 font-mono text-2xl font-medium text-app-text">{value}</p>
    </Card>
  );
}

function SummaryRow({ items }: { items: Array<{ label: string; value: string }> }) {
  return (
    <Card className="overflow-hidden">
      <div className="grid divide-y divide-app-border/70 md:grid-cols-4 md:divide-x md:divide-y-0">
        {items.map((item) => (
          <div key={item.label} className="min-w-0 p-4">
            <p className="truncate text-[11px] font-medium uppercase tracking-[0.18em] text-app-muted">{item.label}</p>
            <p className="mt-2 truncate font-mono text-2xl font-medium text-app-text">{item.value}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

function OpeningsTab({ insights }: { insights: PlayerInsights }) {
  const combined = [...insights.openings.as_white, ...insights.openings.as_black];
  return (
    <div className="grid gap-5 xl:grid-cols-3">
      <ChartCard title="Most common openings">
        <OpeningBar data={combined} dataKey="games" />
      </ChartCard>
      <ChartCard title="Win rate by opening">
        <OpeningBar data={combined} dataKey="win_rate" />
      </ChartCard>
      <ChartCard title="Accuracy by opening">
        <OpeningBar data={combined} dataKey="avg_accuracy" />
      </ChartCard>
      <OpeningTable title="As White" rows={insights.openings.as_white} />
      <OpeningTable title="As Black" rows={insights.openings.as_black} />
    </div>
  );
}

function OpeningBar({ data, dataKey }: { data: OpeningInsight[]; dataKey: keyof OpeningInsight }) {
  const sortedData =
    dataKey === "win_rate"
      ? [...data].sort((a, b) => b.win_rate - a.win_rate)
      : data;
  const chartData = sortedData.slice(0, 10).map((row) => ({ ...row, label: shortLabel(row.opening_name) }));
  const height = Math.max(260, chartData.length * 34 + 44);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={chartData} layout="vertical" margin={{ left: 12, right: 18, top: 8, bottom: 8 }}>
        <CartesianGrid stroke={CHART_GRID} horizontal={false} />
        <XAxis type="number" tick={{ fill: CHART_TEXT, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis
          type="category"
          dataKey="label"
          width={138}
          tick={{ fill: CHART_TEXT, fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          interval={0}
        />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Bar dataKey={dataKey as string} fill={CHART_STROKE} barSize={18} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function MistakesTab({ insights }: { insights: PlayerInsights }) {
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <ChartCard title="Mistakes by game phase">
        <MistakeBar data={insights.mistakes.by_phase} />
      </ChartCard>
      <ChartCard title="Mistake types">
        <MistakeBar data={insights.mistakes.by_type.slice(0, 8)} />
      </ChartCard>
      <Card className="p-5">
        <h3 className="text-base font-medium">Recurring weaknesses</h3>
        <div className="mt-4 grid gap-3">
          {insights.mistakes.top_weaknesses.map((item, index) => (
            <div key={item.category} className="border-b-[0.5px] border-app-border py-3">
              <div className="flex items-center justify-between">
                <span className="font-medium">{index + 1}. {item.category}</span>
                <Badge tone="red">{`${item.percentage}%`}</Badge>
              </div>
              <p className="mt-1 text-sm text-app-muted">{item.count} signals across the sample.</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function MistakeBar({ data }: { data: Array<{ category: string; count: number; percentage: number }> }) {
  const chartData = data.map((row) => ({ ...row, label: shortLabel(row.category) }));
  const height = Math.max(240, chartData.length * 36 + 44);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={chartData} layout="vertical" margin={{ left: 12, right: 18, top: 8, bottom: 8 }}>
        <CartesianGrid stroke={CHART_GRID} horizontal={false} />
        <XAxis type="number" tick={{ fill: CHART_TEXT, fontSize: 11 }} axisLine={false} tickLine={false} allowDecimals={false} />
        <YAxis
          type="category"
          dataKey="label"
          width={138}
          tick={{ fill: CHART_TEXT, fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          interval={0}
        />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Bar dataKey="count" fill={CHART_STROKE} barSize={18} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function ProfileTab({ insights }: { insights: PlayerInsights }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="p-5 lg:col-span-2">
        <h3 className="text-base font-medium">Playstyle summary</h3>
        <p className="mt-3 text-sm leading-6 text-app-muted">{insights.profile.summary}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge tone="blue">{insights.profile.style}</Badge>
          <Badge tone="neutral">{`${insights.profile.position_preference} positions`}</Badge>
          <Badge tone="neutral">{`${insights.profile.average_game_length} avg moves`}</Badge>
        </div>
      </Card>
      <ListCard title="Strengths" rows={insights.profile.strengths} tone="green" />
      <ListCard title="Weaknesses" rows={insights.profile.weaknesses} tone="red" />
      <ListCard title="Recommendations" rows={insights.profile.recommendations} tone="blue" wide />
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="p-5 pb-7">
      <h3 className="mb-4 text-base font-medium">{title}</h3>
      {children}
    </Card>
  );
}

function OpeningTable({ title, rows }: { title: string; rows: OpeningInsight[] }) {
  const sortedRows = [...rows].sort((a, b) => b.win_rate - a.win_rate);

  return (
    <Card className="p-5">
      <h3 className="text-base font-medium">{title}</h3>
      <div className="mt-4 grid gap-2">
        {sortedRows.slice(0, 8).map((row) => (
          <div key={`${row.eco}-${row.opening_name}`} className="grid grid-cols-[1fr_auto] gap-3 border-b-[0.5px] border-app-border py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{row.opening_name}</p>
              <p className="text-xs text-app-muted">{row.eco} · {row.games} games · {row.frequency}%</p>
            </div>
            <div className="min-w-0 overflow-hidden whitespace-nowrap text-right font-mono text-sm text-app-text">{row.win_rate}%</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ResponseList({ title, rows }: { title: string; rows: Array<{ move: string; games: number; frequency: number }> }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-[0.18em] text-app-muted">{title}</p>
      <div className="mt-2 grid gap-2">
        {rows.map((row) => (
          <div key={row.move} className="flex items-center justify-between border-b-[0.5px] border-app-border py-2 text-sm">
            <span className="font-mono">{row.move}</span>
            <span className="text-app-muted">{row.games} · {row.frequency}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ListCard({ title, rows, tone, wide = false }: { title: string; rows: string[]; tone: "green" | "red" | "blue"; wide?: boolean }) {
  return (
    <Card className={`p-5 ${wide ? "lg:col-span-2" : ""}`}>
      <h3 className="text-base font-medium">{title}</h3>
      <div className="mt-4 grid gap-3">
        {rows.map((row) => (
          <div key={row} className="flex gap-3 border-b-[0.5px] border-app-border py-3 text-sm text-app-muted">
            <Badge tone={tone}>{title.slice(0, 1)}</Badge>
            <span>{row}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
