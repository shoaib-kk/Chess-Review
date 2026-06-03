import { useEffect, useMemo, useState } from "react";
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

type TabKey = RepertoireCategory | "trends";
type TrendWindowKey = "last_30" | "last_90" | "last_180" | "all";

const TAB_LABELS: Record<TabKey, string> = {
  white: "White",
  black_vs_e4: "Black vs e4",
  black_vs_d4: "Black vs d4",
  black_vs_other: "Black vs Other",
  trends: "Trends",
};

const BORDER = "border-[0.5px] border-[rgba(0,0,0,0.1)]";
const PANEL = `${BORDER} bg-[#ffffff]`;
const INPUT =
  "h-10 w-full border-[0.5px] border-[rgba(0,0,0,0.1)] bg-[#ffffff] px-3 text-sm font-normal text-[#1a1a1a] outline-none placeholder:text-[#9b9b9b] focus:border-[#1a1a1a]";
const EYEBROW = "text-[11px] font-medium uppercase tracking-[0.18em] text-[#6b6b6b]";
const TITLE = "text-base font-medium text-[#1a1a1a]";
const MUTED = "text-sm font-normal text-[#6b6b6b]";
const NUMBER = "text-right font-mono text-sm text-[#1a1a1a]";
const NEUTRAL = "#1a1a1a";

function fmt(value: number | null | undefined, suffix = "") {
  return value === null || value === undefined ? "-" : `${value.toFixed(1)}${suffix}`;
}

function shortName(value: string) {
  return value.length > 12 ? `${value.slice(0, 9)}...` : value;
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

  useEffect(() => {
    setSelectedOpening(repertoire?.summary.strongest_opening ?? repertoire?.repertoire.white[0] ?? null);
    setActiveTab("white");
  }, [repertoire]);

  async function fetchRepertoire() {
    if (!username.trim()) return;
    const result = await onFetchRepertoire(username.trim(), { limit, time_class: timeClass, rated_only: ratedOnly });
    setSelectedOpening(result?.summary.strongest_opening ?? result?.repertoire.white[0] ?? null);
    setActiveTab("white");
  }

  return (
    <div className="grid gap-5 bg-[#eeeeee] p-5 font-sans font-normal text-[#1a1a1a]">
      <section className={PANEL}>
        <SectionHeader title="Opening Repertoire" eyebrow="Opening-specific performance">
          See which openings you actually play, how often you play them, and how well they perform.
        </SectionHeader>
        <div className="grid gap-3 px-5 pb-5 lg:grid-cols-[1fr_120px_150px_auto_auto] lg:items-center">
          <input
            className={INPUT}
            value={username}
            placeholder="Chess.com username"
            onChange={(event) => onUsernameChange(event.target.value)}
          />
          <input
            className={INPUT}
            type="number"
            min={20}
            max={500}
            value={limit}
            onChange={(event) => onLimitChange(Number(event.target.value))}
          />
          <select
            className={INPUT}
            value={timeClass}
            onChange={(event) => onTimeClassChange(event.target.value as TimeClassFilter)}
          >
            <option value="">All time controls</option>
            <option value="rapid">Rapid</option>
            <option value="blitz">Blitz</option>
            <option value="bullet">Bullet</option>
          </select>
          <label className={`flex h-10 items-center gap-2 px-3 text-sm font-normal text-[#6b6b6b] ${BORDER}`}>
            <input type="checkbox" className="accent-[#1a1a1a]" checked={ratedOnly} onChange={(event) => onRatedOnlyChange(event.target.checked)} />
            Rated only
          </label>
          <PlainButton disabled={!username.trim() || loading} onClick={fetchRepertoire}>
            {loading ? "Loading..." : "Build Repertoire"}
          </PlainButton>
        </div>
      </section>

      {repertoire && (
        <>
          <SummaryRow
            items={[
              { label: "Total Games", value: String(repertoire.summary.total_games) },
              { label: "Openings Tracked", value: String(repertoire.summary.openings_tracked) },
              { label: "Strongest Opening", value: repertoire.summary.strongest_opening?.opening_name ?? "-", detail: fmt(repertoire.summary.strongest_opening?.win_rate, "%") },
              { label: "Weakest Opening", value: repertoire.summary.weakest_opening?.opening_name ?? "-", detail: fmt(repertoire.summary.weakest_opening?.win_rate, "%") },
            ]}
          />

          <RecommendationsPanel repertoire={repertoire} />

          <div className="flex flex-wrap gap-2">
            {(["white", "black_vs_e4", "black_vs_d4", "black_vs_other", "trends"] as const).map((tab) => (
              <PlainButton key={tab} active={activeTab === tab} small onClick={() => setActiveTab(tab)}>
                {TAB_LABELS[tab]}
              </PlainButton>
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

function SectionHeader({ title, eyebrow, children }: { title: string; eyebrow: string; children?: ReactNode }) {
  return (
    <div className="px-5 pb-3 pt-5">
      <p className={EYEBROW}>{eyebrow}</p>
      <h2 className={`${TITLE} mt-1`}>{title}</h2>
      {children && <div className={`${MUTED} mt-1`}>{children}</div>}
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
      className={`inline-flex items-center justify-center border-b-[1px] bg-transparent px-3 text-sm font-medium text-[#1a1a1a] transition hover:bg-[#eeeeee] disabled:cursor-not-allowed disabled:text-[#9b9b9b] ${
        active ? "border-b-[#1a1a1a]" : "border-b-transparent"
      } ${small ? "h-8" : "h-10"}`}
      {...props}
    >
      {children}
    </button>
  );
}

function SummaryRow({ items }: { items: Array<{ label: string; value: string; detail?: string }> }) {
  return (
    <section className={PANEL}>
      <div className="grid divide-y divide-[rgba(0,0,0,0.1)] md:grid-cols-4 md:divide-x md:divide-y-0">
        {items.map((item) => (
          <div key={item.label} className="min-w-0 p-4">
            <p className={`truncate ${EYEBROW}`}>{item.label}</p>
            <p className="mt-2 truncate font-mono text-2xl font-medium text-[#1a1a1a]">{item.value}</p>
            {item.detail && <p className={`${MUTED} mt-1 truncate`}>{item.detail}</p>}
          </div>
        ))}
      </div>
    </section>
  );
}

function RecommendationsPanel({ repertoire }: { repertoire: OpeningRepertoire }) {
  const recommendations = repertoire.recommendations;
  return (
    <section className={`${PANEL} p-5`}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className={EYEBROW}>Recommendations</p>
          <h2 className={`${TITLE} mt-1`}>Opening recommendations</h2>
        </div>
        <SemanticText>
          {recommendations.enough_data ? "Enough data" : "More games needed"}
        </SemanticText>
      </div>
      {recommendations.enough_data ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <RecommendationList title="Continue Playing" rows={recommendations.continue_playing} />
          <RecommendationList title="Needs Improvement" rows={recommendations.needs_improvement} />
          <RecommendationList title="Consider Reviewing" rows={recommendations.consider_reviewing} />
        </div>
      ) : (
        <p className={`${MUTED} mt-4`}>
          Recommendations appear after at least two openings have 10 or more games in the selected sample.
        </p>
      )}
    </section>
  );
}

function SemanticText({ children }: { children: ReactNode }) {
  return (
    <span className="text-sm font-medium text-[#1a1a1a]">
      {children}
    </span>
  );
}

function RecommendationList({ title, rows }: { title: string; rows: OpeningRepertoireRow[] }) {
  return (
    <div className="min-w-0">
      <h3 className="text-sm font-medium text-[#1a1a1a]">{title}</h3>
      <div className="mt-3 grid gap-2 border-t-[0.5px] border-[rgba(0,0,0,0.1)]">
        {rows.map((row) => (
          <div key={`${title}-${row.id}`} className="flex min-w-0 items-start justify-between gap-3 border-b-[0.5px] border-[rgba(0,0,0,0.1)] py-2 text-sm">
            <div className="min-w-0">
              <p className="truncate font-medium text-[#1a1a1a]">{row.opening_name}</p>
              <p className="text-xs font-normal text-[#6b6b6b]">{row.games} games</p>
            </div>
            <span className="shrink-0 whitespace-nowrap font-mono text-sm text-[#1a1a1a]">
              {`${fmt(row.win_rate, "%")} WR`}
            </span>
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
          <OpeningBar data={rows} dataKey="games" />
        </ChartCard>
        <ChartCard title="Win rate by opening">
          <OpeningBar data={rows} dataKey="win_rate" />
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
  const sortedRows = [...rows].sort((a, b) => b.win_rate - a.win_rate);

  return (
    <section className={PANEL}>
      <SectionHeader title={title} eyebrow="Repertoire table">
        Click an opening to inspect recent games, responses, and examples.
      </SectionHeader>
      <div className="overflow-x-auto px-5 pb-5">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-[#f4f4f3] text-[11px] font-medium uppercase tracking-[0.18em] text-[#6b6b6b]">
            <tr>
              <th className="py-2 pl-3 pr-3 font-medium">Opening</th>
              <th className="px-3 py-2 text-right font-medium">Games</th>
              <th className="px-3 py-2 text-right font-medium">Frequency</th>
              <th className="px-3 py-2 text-right font-medium">Win Rate</th>
              <th className="px-3 py-2 text-right font-medium">Accuracy</th>
              <th className="px-3 py-2 text-right font-medium">CP Loss</th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row) => (
              <tr
                key={row.id}
                className={`cursor-pointer border-b-[0.5px] border-[rgba(0,0,0,0.1)] transition hover:bg-[#eeeeee] ${
                  selectedId === row.id ? "outline outline-[0.5px] outline-[#1a1a1a]" : ""
                }`}
                onClick={() => onSelect(row)}
              >
                <td className="max-w-[320px] py-3 pl-3 pr-3">
                  <p className="truncate font-medium text-[#1a1a1a]">{row.opening_name}</p>
                  <p className="text-xs font-normal text-[#6b6b6b]">{row.eco}</p>
                </td>
                <td className={`px-3 py-3 ${NUMBER}`}>{row.games}</td>
                <td className={`px-3 py-3 ${NUMBER}`}>{fmt(row.frequency, "%")}</td>
                <td className={`whitespace-nowrap px-3 py-3 ${NUMBER}`}>{fmt(row.win_rate, "%")}</td>
                <td className={`px-3 py-3 ${NUMBER}`}>{fmt(row.avg_accuracy)}</td>
                <td className={`px-3 py-3 ${NUMBER}`}>{fmt(row.avg_cp_loss, " cp")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p className={`${MUTED} py-6`}>No openings in this category for the selected filters.</p>}
      </div>
    </section>
  );
}

function OpeningBar({ data, dataKey }: { data: OpeningRepertoireRow[]; dataKey: keyof OpeningRepertoireRow }) {
  const sortedData =
    dataKey === "win_rate"
      ? [...data].sort((a, b) => b.win_rate - a.win_rate)
      : data;

  return (
    <ResponsiveContainer width="100%" height={292}>
      <BarChart data={sortedData.slice(0, 10).map((row) => ({ ...row, label: shortName(row.opening_name) }))} margin={{ left: -20, right: 8, top: 8, bottom: 72 }}>
        <CartesianGrid stroke="rgba(0,0,0,0.1)" vertical={false} />
        <XAxis dataKey="label" tick={{ fill: "#6b6b6b", fontSize: 10, fontWeight: 400 }} angle={-25} textAnchor="end" interval={0} height={72} />
        <YAxis tick={{ fill: "#6b6b6b", fontSize: 11, fontWeight: 400 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={{ background: "#ffffff", border: "0.5px solid rgba(0,0,0,0.1)", borderRadius: 0, color: "#1a1a1a" }} />
        <Bar dataKey={dataKey as string} fill={NEUTRAL} />
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
      <section className={`${PANEL} p-5`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className={EYEBROW}>Trend window</p>
            <h2 className={`${TITLE} mt-1`}>{window.games} games in sample</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {(["last_30", "last_90", "last_180", "all"] as const).map((key) => (
              <PlainButton key={key} active={windowKey === key} small onClick={() => setWindowKey(key)}>
                {key === "all" ? "All games" : key.replace("_", " ")}
              </PlainButton>
            ))}
          </div>
        </div>
      </section>
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
          <TrendLine data={repertoire.trends.points} dataKey="accuracy" stroke={NEUTRAL} />
        </ChartCard>
        <ChartCard title="Result rate over games">
          <TrendLine data={repertoire.trends.points} dataKey="win_rate" stroke={NEUTRAL} />
        </ChartCard>
      </div>
    </div>
  );
}

function TrendLine({ data, dataKey, stroke }: { data: OpeningTrendPoint[]; dataKey: "accuracy" | "win_rate"; stroke: string }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ left: -20, right: 8, top: 8, bottom: 8 }}>
        <CartesianGrid stroke="rgba(0,0,0,0.1)" vertical={false} />
        <XAxis dataKey="game_index" tick={{ fill: "#6b6b6b", fontSize: 10, fontWeight: 400 }} minTickGap={24} />
        <YAxis tick={{ fill: "#6b6b6b", fontSize: 11, fontWeight: 400 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={{ background: "#ffffff", border: "0.5px solid rgba(0,0,0,0.1)", borderRadius: 0, color: "#1a1a1a" }} />
        <Line type="monotone" dataKey={dataKey} stroke={stroke} strokeWidth={1.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function OpeningExplorer({ opening }: { opening: OpeningRepertoireRow | null }) {
  if (!opening) {
    return (
      <section className={`${PANEL} p-5`}>
        <h2 className={TITLE}>Opening Explorer</h2>
        <p className={`${MUTED} mt-2`}>Select an opening from a table to inspect it.</p>
      </section>
    );
  }

  return (
    <section className={PANEL}>
      <SectionHeader title="Opening Explorer" eyebrow="Selected opening">
        {opening.eco} - {opening.opening_name}
      </SectionHeader>
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
    </section>
  );
}

function CompareOpenings({ rows }: { rows: OpeningRepertoireRow[] }) {
  const [openingA, setOpeningA] = useState("");
  const [openingB, setOpeningB] = useState("");
  const first = rows.find((row) => row.id === openingA) ?? rows[0];
  const second = rows.find((row) => row.id === openingB) ?? rows[1];

  return (
    <section className={`${PANEL} p-5`}>
      <p className={EYEBROW}>Bonus</p>
      <h2 className={`${TITLE} mt-1`}>Compare Openings</h2>
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
        <p className={`${MUTED} mt-4`}>At least two openings are needed for comparison.</p>
      )}
    </section>
  );
}

function OpeningSelect({ rows, value, onChange }: { rows: OpeningRepertoireRow[]; value: string; onChange: (value: string) => void }) {
  return (
    <select
      className={`${INPUT} min-w-0`}
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
    <div className="grid grid-cols-[1fr_0.8fr_0.8fr] items-center gap-3 border-b-[0.5px] border-[rgba(0,0,0,0.1)] py-2 text-sm">
      <span className="font-normal text-[#6b6b6b]">{label}</span>
      <span className="text-right font-mono text-[#1a1a1a]">{a}</span>
      <span className="text-right font-mono text-[#1a1a1a]">{b}</span>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className={`${BORDER} p-3`}>
      <p className={EYEBROW}>{label}</p>
      <p className="mt-2 text-right font-mono text-lg font-medium text-[#1a1a1a]">{value}</p>
    </div>
  );
}

function StatList({ title, rows }: { title: string; rows: string[] }) {
  return (
    <div className={`${BORDER} p-4`}>
      <h3 className="text-sm font-medium text-[#1a1a1a]">{title}</h3>
      <div className="mt-3 grid gap-2 text-sm font-normal text-[#6b6b6b]">
        {rows.length ? rows.map((row) => <p key={row}>{row}</p>) : <p className="text-[#9b9b9b]">No data yet.</p>}
      </div>
    </div>
  );
}

function GameList({ title, rows }: { title: string; rows: OpeningGameExample[] }) {
  return (
    <div className={`${BORDER} p-4`}>
      <h3 className="text-sm font-medium text-[#1a1a1a]">{title}</h3>
      <div className="mt-3 grid">
        {rows.length ? (
          rows.map((row, index) => (
            <a
              key={`${title}-${row.url ?? index}`}
              className="grid grid-cols-[1fr_auto] gap-3 border-b-[0.5px] border-[rgba(0,0,0,0.1)] py-2 text-sm transition hover:bg-[#eeeeee]"
              href={row.url ?? undefined}
              target="_blank"
              rel="noreferrer"
            >
              <span className="min-w-0 truncate font-normal text-[#1a1a1a]">
                {row.date ?? "Unknown date"} vs {row.opponent}
              </span>
              <span className="text-right font-mono text-[#6b6b6b]">{row.result}</span>
            </a>
          ))
        ) : (
          <p className={`${MUTED} py-2`}>No games available.</p>
        )}
      </div>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={`${PANEL} p-5 pb-7`}>
      <h3 className={`${TITLE} mb-4`}>{title}</h3>
      {children}
    </section>
  );
}
