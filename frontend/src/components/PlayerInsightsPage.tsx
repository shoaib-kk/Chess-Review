import { useState } from "react";
import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Cell,
} from "recharts";
import type { OpeningInsight, PlayerInsights } from "../types";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";
import { Badge } from "./ui/Badge";

interface PlayerInsightsPageProps {
  loading: boolean;
  onFetchInsights: (
    username: string,
    params: { limit: number; time_class: "rapid" | "blitz" | "bullet" | ""; rated_only: boolean },
  ) => Promise<PlayerInsights | null>;
  initialUsername?: string | null;
}

const PIE_COLORS = ["#3b82f6", "#ef4444", "#f97316", "#eab308", "#22c55e", "#8b5cf6", "#14b8a6", "#f43f5e"];

function fmt(value: number | null | undefined, suffix = "") {
  return value === null || value === undefined ? "-" : `${value.toFixed(1)}${suffix}`;
}

export function PlayerInsightsPage({ loading, onFetchInsights, initialUsername }: PlayerInsightsPageProps) {
  const [username, setUsername] = useState(initialUsername ?? "");
  const [limit, setLimit] = useState(200);
  const [timeClass, setTimeClass] = useState<"rapid" | "blitz" | "bullet" | "">("");
  const [ratedOnly, setRatedOnly] = useState(false);
  const [insights, setInsights] = useState<PlayerInsights | null>(null);
  const [activeTab, setActiveTab] = useState<"openings" | "trends" | "mistakes" | "profile">("openings");

  async function fetchInsights() {
    if (!username.trim()) return;
    const result = await onFetchInsights(username.trim(), { limit, time_class: timeClass, rated_only: ratedOnly });
    setInsights(result);
  }

  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader title="Player Insights" eyebrow="Chess.com history">
          High-level opening habits, trends, weaknesses, and recommendations.
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
            max={300}
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          />
          <select
            className="h-11 rounded-md bg-slate-950/80 px-3 text-app-text outline-none ring-1 ring-app-border focus:ring-2 focus:ring-app-accent/70"
            value={timeClass}
            onChange={(event) => setTimeClass(event.target.value as "rapid" | "blitz" | "bullet" | "")}
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
          <Button variant="primary" disabled={!username.trim() || loading} onClick={fetchInsights}>
            {loading ? "Loading..." : "Generate Insights"}
          </Button>
        </div>
      </Card>

      {insights && (
        <>
          <section className="grid gap-3 md:grid-cols-4">
            <SummaryCard label="Games Analyzed" value={String(insights.summary.games_analyzed)} />
            <SummaryCard label="Win Rate" value={fmt(insights.summary.win_rate, "%")} />
            <SummaryCard label="Average Accuracy" value={fmt(insights.summary.average_accuracy)} />
            <SummaryCard label="Average CP Loss" value={fmt(insights.summary.average_cp_loss, " cp")} />
          </section>

          <div className="flex flex-wrap gap-2">
            {(["openings", "trends", "mistakes", "profile"] as const).map((tab) => (
              <Button key={tab} variant={activeTab === tab ? "primary" : "secondary"} size="sm" onClick={() => setActiveTab(tab)}>
                {tab[0].toUpperCase() + tab.slice(1)}
              </Button>
            ))}
          </div>

          {activeTab === "openings" && <OpeningsTab insights={insights} />}
          {activeTab === "trends" && <TrendsTab insights={insights} />}
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
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-app-muted">{label}</p>
      <p className="mt-2 font-mono text-2xl font-black text-app-text">{value}</p>
    </Card>
  );
}

function OpeningsTab({ insights }: { insights: PlayerInsights }) {
  const combined = [...insights.openings.as_white, ...insights.openings.as_black].slice(0, 10);
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
      <Card className="p-5">
        <h3 className="text-base font-semibold">Black responses</h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <ResponseList title="vs e4" rows={insights.openings.responses_to_e4} />
          <ResponseList title="vs d4" rows={insights.openings.responses_to_d4} />
        </div>
      </Card>
    </div>
  );
}

function OpeningBar({ data, dataKey }: { data: OpeningInsight[]; dataKey: keyof OpeningInsight }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ left: -20, right: 8, top: 8, bottom: 40 }}>
        <CartesianGrid stroke="#263244" strokeDasharray="3 6" vertical={false} />
        <XAxis dataKey="opening_name" tick={{ fill: "#94a3b8", fontSize: 10 }} angle={-25} textAnchor="end" interval={0} height={68} />
        <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={{ background: "#111827", border: "1px solid #263244", borderRadius: 8 }} />
        <Bar dataKey={dataKey as string} fill="#3b82f6" radius={[5, 5, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function TrendsTab({ insights }: { insights: PlayerInsights }) {
  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <ChartCard title="Accuracy over time">
        <TrendLine data={insights.performance.trend_points} dataKey="accuracy" stroke="#22c55e" />
      </ChartCard>
      <ChartCard title="Average CP loss over time">
        <TrendLine data={insights.performance.trend_points} dataKey="cp_loss" stroke="#f97316" />
      </ChartCard>
      <ChartCard title="Blunders over time">
        <TrendLine data={insights.performance.trend_points} dataKey="blunders" stroke="#ef4444" />
      </ChartCard>
      <ChartCard title="Rating over time">
        <TrendLine data={insights.performance.rating_points} dataKey="rating" stroke="#3b82f6" />
      </ChartCard>
      <Card className="p-5 xl:col-span-2">
        <h3 className="text-base font-semibold">Trend notes</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          {insights.performance.trend_notes.map((note) => <Badge key={note} tone="blue">{note}</Badge>)}
        </div>
      </Card>
    </div>
  );
}

function TrendLine({ data, dataKey, stroke }: { data: Array<Record<string, unknown>>; dataKey: string; stroke: string }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ left: -20, right: 8, top: 8, bottom: 8 }}>
        <CartesianGrid stroke="#263244" strokeDasharray="3 6" vertical={false} />
        <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 10 }} minTickGap={24} />
        <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={{ background: "#111827", border: "1px solid #263244", borderRadius: 8 }} />
        <Line type="monotone" dataKey={dataKey} stroke={stroke} strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function MistakesTab({ insights }: { insights: PlayerInsights }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_0.8fr]">
      <ChartCard title="Mistake category distribution">
        <ResponsiveContainer width="100%" height={320}>
          <PieChart>
            <Pie data={insights.mistakes.categories} dataKey="count" nameKey="category" innerRadius={70} outerRadius={115} paddingAngle={3}>
              {insights.mistakes.categories.map((_, index) => <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />)}
            </Pie>
            <Tooltip contentStyle={{ background: "#111827", border: "1px solid #263244", borderRadius: 8 }} />
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>
      <Card className="p-5">
        <h3 className="text-base font-semibold">Recurring weaknesses</h3>
        <div className="mt-4 grid gap-3">
          {insights.mistakes.top_weaknesses.map((item, index) => (
            <div key={item.category} className="rounded-md bg-slate-950/70 p-4 ring-1 ring-app-border">
              <div className="flex items-center justify-between">
                <span className="font-semibold">{index + 1}. {item.category}</span>
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

function ProfileTab({ insights }: { insights: PlayerInsights }) {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="p-5 lg:col-span-2">
        <h3 className="text-base font-semibold">Playstyle summary</h3>
        <p className="mt-3 text-sm leading-6 text-slate-300">{insights.profile.summary}</p>
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
    <Card className="p-5">
      <h3 className="mb-4 text-base font-semibold">{title}</h3>
      {children}
    </Card>
  );
}

function OpeningTable({ title, rows }: { title: string; rows: OpeningInsight[] }) {
  return (
    <Card className="p-5">
      <h3 className="text-base font-semibold">{title}</h3>
      <div className="mt-4 grid gap-2">
        {rows.slice(0, 8).map((row) => (
          <div key={`${row.eco}-${row.opening_name}`} className="grid grid-cols-[1fr_auto] gap-3 rounded-md bg-slate-950/70 p-3 ring-1 ring-app-border">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{row.opening_name}</p>
              <p className="text-xs text-app-muted">{row.eco} · {row.games} games · {row.frequency}%</p>
            </div>
            <div className="text-right font-mono text-sm text-app-text">{row.win_rate}%</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ResponseList({ title, rows }: { title: string; rows: Array<{ move: string; games: number; frequency: number }> }) {
  return (
    <div>
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-app-muted">{title}</p>
      <div className="mt-2 grid gap-2">
        {rows.map((row) => (
          <div key={row.move} className="flex items-center justify-between rounded bg-slate-950/70 px-3 py-2 text-sm">
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
      <h3 className="text-base font-semibold">{title}</h3>
      <div className="mt-4 grid gap-3">
        {rows.map((row) => (
          <div key={row} className="flex gap-3 rounded-md bg-slate-950/70 p-3 text-sm text-slate-300 ring-1 ring-app-border">
            <Badge tone={tone}>{title.slice(0, 1)}</Badge>
            <span>{row}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
