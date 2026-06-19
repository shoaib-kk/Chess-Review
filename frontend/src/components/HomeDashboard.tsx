import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpen,
  ChevronRight,
  Download,
  FileText,
  Flame,
  Gauge,
  Play,
  Puzzle,
  Sparkles,
  Target,
  TrendingUp,
  Trophy,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { fetchChessComGames, fetchPlayerInsights, fetchPuzzles } from "../api/client";
import type { ChessComGame, GameSummary, OpeningInsight, PlayerInsights, PuzzleList } from "../types";
import { SAMPLE_GAME_LABEL } from "../data/sampleGame";
import { ApiStatusIndicator } from "./ApiStatusIndicator";
import { Button } from "./ui/Button";
import { ChessGlyph } from "./ui/ChessGlyph";
import { Delta } from "./ui/Delta";
import { ProgressRing } from "./ui/ProgressRing";
import { SectionHeading } from "./ui/SectionHeading";
import { Skeleton } from "./ui/Skeleton";
import { Sparkline } from "./ui/Sparkline";
import { StatCard } from "./ui/StatCard";
import { Surface } from "./ui/Surface";
import { WinLossBar } from "./ui/WinLossBar";

interface HomeDashboardProps {
  apiStatus: "checking" | "ok" | "down";
  username: string;
  onUsernameChange: (username: string) => void;
  onImportGame: () => void;
  onPastePgn: () => void;
  onTrySample: () => void;
  onOpenInsights: () => void;
  onOpenRepertoire: () => void;
  onOpenPuzzles: () => void;
  sampleLoading: boolean;
  activeReview: GameSummary | null;
  onResumeReview: () => void;
  onReviewGame: (game: ChessComGame) => void;
}

// ── helpers ──────────────────────────────────────────────────────────────────
function fmt1(value: number | null | undefined, suffix = "") {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}${suffix}`;
}
function fmt0(value: number | null | undefined, suffix = "") {
  return value === null || value === undefined ? "—" : `${Math.round(value)}${suffix}`;
}
function greeting() {
  const h = new Date().getHours();
  if (h < 5) return "Burning the midnight oil";
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}
function userOutcome(game: ChessComGame, username: string): "win" | "loss" | "draw" {
  const isWhite = game.white_username?.toLowerCase() === username.toLowerCase();
  if (game.result === "1/2-1/2") return "draw";
  const whiteWon = game.result === "1-0";
  if (whiteWon) return isWhite ? "win" : "loss";
  return isWhite ? "loss" : "win";
}

interface DashData {
  insights: PlayerInsights | null;
  puzzles: PuzzleList | null;
  games: ChessComGame[];
}

export function HomeDashboard(props: HomeDashboardProps) {
  const { username } = props;
  const hasUsername = Boolean(username.trim());

  const [data, setData] = useState<DashData>({ insights: null, puzzles: null, games: [] });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const name = username.trim();
    if (!name) {
      setData({ insights: null, puzzles: null, games: [] });
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.allSettled([
      fetchPlayerInsights(name, { limit: 200 }),
      fetchPuzzles(name, { limit: 1 }),
      fetchChessComGames(name, 12),
    ]).then(([insightsRes, puzzlesRes, gamesRes]) => {
      if (cancelled) return;
      setData({
        insights: insightsRes.status === "fulfilled" ? insightsRes.value : null,
        puzzles: puzzlesRes.status === "fulfilled" ? puzzlesRes.value : null,
        games: gamesRes.status === "fulfilled" ? gamesRes.value : [],
      });
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [username]);

  if (!hasUsername) {
    return <Onboarding {...props} />;
  }

  return (
    <div className="mx-auto w-full max-w-[1180px] animate-rise pb-12">
      <DashboardHeader {...props} insights={data.insights} loading={loading} />
      {loading && !data.insights ? (
        <DashboardSkeleton />
      ) : (
        <DashboardBody {...props} data={data} />
      )}
    </div>
  );
}

// ── header ───────────────────────────────────────────────────────────────────
function DashboardHeader({
  username,
  apiStatus,
  activeReview,
  onResumeReview,
  onImportGame,
  insights,
  loading,
}: HomeDashboardProps & { insights: PlayerInsights | null; loading: boolean }) {
  const games = insights?.summary.games_analyzed;
  return (
    <header className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <p className="mb-1.5 flex items-center gap-2 text-xs font-medium text-app-subtle">
          <Sparkles className="h-3.5 w-3.5 text-app-accent" />
          {greeting()}
        </p>
        <h1 className="text-[28px] font-semibold leading-tight tracking-tightest text-app-text">
          Welcome back, <span className="text-app-accent">{username.trim()}</span>
        </h1>
        <p className="mt-1.5 text-sm text-app-muted">
          {loading
            ? "Pulling your latest games and analysis…"
            : games
              ? `Here's what's happened across your last ${games} games.`
              : "Import a game to start building your profile."}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <ApiStatusIndicator status={apiStatus} />
        {activeReview ? (
          <Button variant="primary" size="md" onClick={onResumeReview}>
            <Play className="h-4 w-4" />
            Resume review
          </Button>
        ) : (
          <Button variant="primary" size="md" onClick={onImportGame}>
            <Download className="h-4 w-4" />
            New review
          </Button>
        )}
      </div>
    </header>
  );
}

// ── body ─────────────────────────────────────────────────────────────────────
function DashboardBody({
  data,
  onOpenInsights,
  onOpenRepertoire,
  onOpenPuzzles,
  onImportGame,
  onPastePgn,
  onReviewGame,
  activeReview,
  onResumeReview,
  username,
}: HomeDashboardProps & { data: DashData }) {
  const { insights, puzzles, games } = data;
  const s = insights?.summary;
  const perf = insights?.performance;

  const accuracySeries = useMemo(
    () => (perf?.trend_points ?? []).map((p) => p.accuracy).filter((n) => Number.isFinite(n)),
    [perf],
  );
  const ratingSeries = useMemo(() => (perf?.rating_points ?? []).map((p) => p.rating), [perf]);

  const accuracyDelta =
    perf && perf.last_30.avg_accuracy != null && perf.last_90.avg_accuracy != null
      ? perf.last_30.avg_accuracy - perf.last_90.avg_accuracy
      : null;
  const winRateDelta = perf ? perf.last_30.win_rate - perf.last_90.win_rate : null;
  const currentRating = ratingSeries.length ? ratingSeries[ratingSeries.length - 1] : null;
  const ratingDelta = ratingSeries.length > 1 ? currentRating! - ratingSeries[0] : null;

  const openings = useMemo(
    () => [...(insights?.openings.as_white ?? []), ...(insights?.openings.as_black ?? [])],
    [insights],
  );
  const favourite = useMemo(
    () => openings.slice().sort((a, b) => b.games - a.games)[0] ?? null,
    [openings],
  );
  const weakest = useMemo(() => {
    const eligible = openings.filter((o) => o.games >= 3);
    const pool = eligible.length ? eligible : openings;
    return pool.slice().sort((a, b) => a.win_rate - b.win_rate)[0] ?? null;
  }, [openings]);

  const focusText = weakest?.opening_family ?? null;

  const puzzleCount = puzzles?.total_puzzles ?? puzzles?.progress.puzzle_count ?? 0;

  return (
    <div className="space-y-7">
      {/* Hero row: focus / resume + accuracy ring */}
      <div className="grid gap-4 lg:grid-cols-12">
        <FocusCard
          className="lg:col-span-8"
          activeReview={activeReview}
          onResumeReview={onResumeReview}
          focusText={focusText}
          onOpenPuzzles={onOpenPuzzles}
          onOpenInsights={onOpenInsights}
          puzzleCount={puzzleCount}
        />
        <AccuracyCard
          className="lg:col-span-4"
          accuracy={s?.average_accuracy ?? null}
          delta={accuracyDelta}
          series={accuracySeries}
        />
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <StatCard
          label="Rating"
          value={currentRating ?? "—"}
          icon={TrendingUp}
          delta={ratingDelta}
          deltaSuffix=""
          caption={currentRating ? "live" : "no data"}
          visual={ratingSeries.length > 1 ? <Sparkline data={ratingSeries} width={84} height={32} /> : undefined}
        />
        <StatCard
          label="Win rate"
          value={fmt0(s?.win_rate)}
          unit="%"
          icon={Trophy}
          delta={winRateDelta}
          deltaSuffix="%"
          caption={`across ${s?.games_analyzed ?? 0}`}
        />
        <StatCard
          label="Games analysed"
          value={s?.games_analyzed ?? 0}
          icon={Activity}
          caption={s?.games_with_accuracy ? `${s.games_with_accuracy} with accuracy` : undefined}
        />
      </div>

      {/* Trend */}
      <div className="grid gap-4 lg:grid-cols-12">
        <TrendPanel className="lg:col-span-12" insights={insights} />
      </div>

      {/* Discovery cards */}
      <div>
        <SectionHeading eyebrow="Your repertoire" title="Openings & training" />
        <div className="grid gap-4 md:grid-cols-3">
          <OpeningCard
            tone="favourite"
            opening={favourite}
            onExplore={onOpenRepertoire}
          />
          <OpeningCard tone="weakest" opening={weakest} onExplore={onOpenRepertoire} />
          <PuzzleCard puzzles={puzzles} count={puzzleCount} onOpenPuzzles={onOpenPuzzles} />
        </div>
      </div>

      {/* Recent games + coach notes */}
      <div className="grid gap-4 lg:grid-cols-12">
        <RecentGames
          className="lg:col-span-8"
          games={games}
          username={username}
          onReviewGame={onReviewGame}
          onImportGame={onImportGame}
        />
        <CoachNotes className="lg:col-span-4" insights={insights} onPastePgn={onPastePgn} />
      </div>
    </div>
  );
}

// ── hero cards ─────────────────────────────────────────────────────────────
function FocusCard({
  className = "",
  activeReview,
  onResumeReview,
  focusText,
  onOpenPuzzles,
  onOpenInsights,
  puzzleCount,
}: {
  className?: string;
  activeReview: GameSummary | null;
  onResumeReview: () => void;
  focusText: string | null;
  onOpenPuzzles: () => void;
  onOpenInsights: () => void;
  puzzleCount: number;
}) {
  if (activeReview) {
    const opening = activeReview.opening_name || `${activeReview.white_player} vs ${activeReview.black_player}`;
    const accuracy = activeReview.user_accuracy ?? activeReview.white_accuracy;
    return (
      <Surface variant="raised" className={`relative overflow-hidden p-6 ${className}`}>
        <div className="pointer-events-none absolute -right-8 -top-10 text-[140px] leading-none text-white/[0.03]">
          <ChessGlyph piece="king" />
        </div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-accent/80">Continue where you left off</p>
        <h3 className="mt-2 text-xl font-semibold tracking-tight text-app-text">{opening}</h3>
        <p className="mt-1 text-sm text-app-muted">
          {activeReview.user_username
            ? `${activeReview.user_username} as ${activeReview.user_color} · ${activeReview.result}`
            : `${activeReview.white_player} vs ${activeReview.black_player} · ${activeReview.result}`}
        </p>
        <div className="mt-5 flex flex-wrap items-center gap-6">
          <Stat label="Accuracy" value={fmt1(accuracy, "%")} />
          <Stat label="Moves" value={String(activeReview.total_moves)} />
          <Stat
            label="Blunders"
            value={String(activeReview.user_blunders ?? activeReview.white_blunders + activeReview.black_blunders)}
            tone="blunder"
          />
        </div>
        <Button variant="primary" size="md" className="mt-6" onClick={onResumeReview}>
          <Play className="h-4 w-4" />
          Resume review
        </Button>
      </Surface>
    );
  }

  return (
    <Surface variant="raised" className={`relative overflow-hidden p-6 ${className}`}>
      <div className="pointer-events-none absolute -right-6 -top-8 text-[130px] leading-none text-app-accent/[0.06]">
        <ChessGlyph piece="knight" />
      </div>
      <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-app-accent/80">
        <Target className="h-3.5 w-3.5" />
        Today's improvement focus
      </p>
      <h3 className="mt-2 max-w-md text-xl font-semibold leading-snug tracking-tight text-app-text">
        {focusText
          ? `Your biggest leak right now is ${focusText.toLowerCase()}.`
          : "Train tactics drawn from your own blunders."}
      </h3>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-app-muted">
        {focusText
          ? "Drill the moments where it shows up, then check whether your accuracy trend responds."
          : "The more games you import, the sharper your personalised plan becomes."}
      </p>
      <div className="mt-6 flex flex-wrap gap-2.5">
        <Button variant="primary" size="md" onClick={onOpenPuzzles}>
          <Puzzle className="h-4 w-4" />
          {puzzleCount > 0 ? `Train ${puzzleCount} puzzles` : "Generate puzzles"}
        </Button>
        <Button variant="secondary" size="md" onClick={onOpenInsights}>
          View full report
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </Surface>
  );
}

function AccuracyCard({
  className = "",
  accuracy,
  delta,
  series,
}: {
  className?: string;
  accuracy: number | null;
  delta: number | null;
  series: number[];
}) {
  return (
    <Surface className={`flex flex-col items-center justify-center gap-4 p-6 ${className}`}>
      <div className="flex w-full items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-app-subtle">Accuracy</span>
        <Gauge className="h-4 w-4 text-app-faint" />
      </div>
      <ProgressRing value={accuracy ?? 0} size={140} strokeWidth={10}>
        <span className="text-3xl font-semibold tracking-tightest text-app-text nums">{fmt1(accuracy)}</span>
        <span className="text-xs text-app-subtle">out of 100</span>
      </ProgressRing>
      <div className="flex items-center gap-2">
        {delta != null ? <Delta value={delta} suffix="%" /> : <span className="text-xs text-app-subtle">—</span>}
        <span className="text-xs text-app-muted">vs 90-day avg</span>
      </div>
      {series.length > 1 && <Sparkline data={series} width={200} height={32} />}
    </Surface>
  );
}

// ── trend chart ───────────────────────────────────────────────────────────
function TrendPanel({ className = "", insights }: { className?: string; insights: PlayerInsights | null }) {
  const [metric, setMetric] = useState<"accuracy" | "rating">("accuracy");
  const points = insights?.performance.trend_points ?? [];
  const ratingPts = insights?.performance.rating_points ?? [];

  const chartData =
    metric === "accuracy"
      ? points.map((p, i) => ({ i, value: p.accuracy }))
      : (ratingPts.length ? ratingPts : points).map((p: { rating: number | null }, i) => ({ i, value: p.rating }));

  const hasData = chartData.filter((d) => d.value != null).length > 1;

  return (
    <Surface className={`flex flex-col p-5 ${className}`}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-app-subtle">Performance trend</p>
          <p className="mt-0.5 text-sm text-app-muted">{metric === "accuracy" ? "Accuracy per game" : "Rating over time"}</p>
        </div>
        <Segmented
          value={metric}
          onChange={(v) => setMetric(v as "accuracy" | "rating")}
          options={[
            { value: "accuracy", label: "Accuracy" },
            { value: "rating", label: "Rating" },
          ]}
        />
      </div>
      {hasData ? (
        <div className="h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#c8a15a" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#c8a15a" stopOpacity={0} />
                </linearGradient>
              </defs>
              <YAxis hide domain={["dataMin - 2", "dataMax + 2"]} />
              <Tooltip
                cursor={{ stroke: "rgba(255,255,255,0.12)", strokeWidth: 1 }}
                contentStyle={{
                  background: "#191a1e",
                  border: "1px solid #34363d",
                  borderRadius: 10,
                  fontSize: 12,
                  color: "#f3f3f5",
                  boxShadow: "0 16px 48px -16px rgba(0,0,0,0.7)",
                }}
                labelFormatter={() => ""}
                formatter={(value: number) => [metric === "accuracy" ? `${value?.toFixed?.(1)}%` : value, metric === "accuracy" ? "Accuracy" : "Rating"]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#c8a15a"
                strokeWidth={2}
                fill="url(#trendFill)"
                dot={false}
                activeDot={{ r: 4, fill: "#c8a15a", stroke: "#0a0a0c", strokeWidth: 2 }}
                connectNulls
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <EmptyHint icon={TrendingUp} text="Not enough games yet to chart a trend." />
      )}
    </Surface>
  );
}

// ── opening + puzzle cards ──────────────────────────────────────────────────
function OpeningCard({
  tone,
  opening,
  onExplore,
}: {
  tone: "favourite" | "weakest";
  opening: OpeningInsight | null;
  onExplore: () => void;
}) {
  const isFav = tone === "favourite";
  const label = isFav ? "Most played" : "Needs work";
  const Icon = isFav ? Flame : Target;
  const accent = isFav ? "text-app-accent" : "text-app-mistake";

  if (!opening) {
    return (
      <Surface className="p-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-app-subtle">{label}</p>
        <EmptyHint icon={BookOpen} text="No opening data yet." />
      </Surface>
    );
  }

  const wins = Math.round((opening.win_rate / 100) * opening.games);
  const losses = opening.games - wins;

  return (
    <Surface
      as="button"
      interactive
      onClick={onExplore}
      className="group flex w-full flex-col p-5"
    >
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-app-subtle">{label}</p>
        <Icon className={`h-4 w-4 ${accent}`} />
      </div>
      <h3 className="mt-3 truncate text-lg font-semibold tracking-tight text-app-text">{opening.opening_family}</h3>
      <p className="mt-0.5 truncate text-xs text-app-subtle">
        {opening.eco}
        {opening.variation ? ` · ${opening.variation}` : ""}
      </p>
      <div className="mt-4 flex items-end justify-between">
        <div>
          <span className="text-2xl font-semibold tracking-tightest text-app-text nums">{fmt0(opening.win_rate)}%</span>
          <span className="ml-1.5 text-xs text-app-muted">win rate</span>
        </div>
        <span className="nums text-xs text-app-subtle">{opening.games} games</span>
      </div>
      <WinLossBar wins={wins} draws={0} losses={losses} className="mt-3" />
      <span className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-app-accent opacity-0 transition group-hover:opacity-100">
        Explore <ChevronRight className="h-3.5 w-3.5" />
      </span>
    </Surface>
  );
}

function PuzzleCard({
  puzzles,
  count,
  onOpenPuzzles,
}: {
  puzzles: PuzzleList | null;
  count: number;
  onOpenPuzzles: () => void;
}) {
  const phases = puzzles?.phase_counts;
  return (
    <Surface as="button" interactive onClick={onOpenPuzzles} className="group flex w-full flex-col p-5">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-app-subtle">Your puzzles</p>
        <Puzzle className="h-4 w-4 text-app-accent" />
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-3xl font-semibold tracking-tightest text-app-text nums">{count}</span>
        <span className="text-sm text-app-muted">{count === 1 ? "tactic" : "tactics"} ready</span>
      </div>
      <p className="mt-1 text-xs text-app-subtle">Built from your own mistakes</p>
      {phases && count > 0 ? (
        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          <PhasePill label="Opening" value={phases.opening} />
          <PhasePill label="Middle" value={phases.middlegame} />
          <PhasePill label="Endgame" value={phases.endgame} />
        </div>
      ) : (
        <p className="mt-4 text-xs text-app-muted">Generate puzzles from your recent games.</p>
      )}
      <span className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-app-accent">
        {count > 0 ? "Continue training" : "Generate puzzles"} <ChevronRight className="h-3.5 w-3.5" />
      </span>
    </Surface>
  );
}

function PhasePill({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-app-border bg-app-bgInset py-2">
      <div className="nums text-sm font-semibold text-app-text">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-app-subtle">{label}</div>
    </div>
  );
}

// ── recent games + coach notes ───────────────────────────────────────────────
function RecentGames({
  className = "",
  games,
  username,
  onReviewGame,
  onImportGame,
}: {
  className?: string;
  games: ChessComGame[];
  username: string;
  onReviewGame: (game: ChessComGame) => void;
  onImportGame: () => void;
}) {
  const recent = games.slice(0, 6);
  return (
    <Surface className={`p-5 ${className}`}>
      <SectionHeading
        title="Recent games"
        action={
          <button onClick={onImportGame} className="text-xs font-medium text-app-accent hover:text-app-accentHover">
            View all
          </button>
        }
      />
      {recent.length ? (
        <ul className="-mx-2 mt-1 divide-y divide-app-border/70">
          {recent.map((game, idx) => {
            const outcome = userOutcome(game, username);
            const opponent =
              game.white_username?.toLowerCase() === username.toLowerCase() ? game.black_username : game.white_username;
            const isWhite = game.white_username?.toLowerCase() === username.toLowerCase();
            return (
              <li key={game.url ?? idx}>
                <button
                  onClick={() => onReviewGame(game)}
                  className="focus-ring group flex w-full items-center gap-3 rounded-lg px-2 py-2.5 text-left transition hover:bg-white/[0.03]"
                >
                  <ResultBadge outcome={outcome} />
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md border border-app-border bg-app-bgInset text-xs">
                    <ChessGlyph piece="pawn" className={isWhite ? "text-app-text" : "text-app-subtle"} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-app-text">vs {opponent || "Unknown"}</span>
                    <span className="block truncate text-xs text-app-subtle">
                      {game.time_class ?? "—"}
                      {game.date ? ` · ${game.date}` : ""}
                      {game.rated ? "" : " · casual"}
                    </span>
                  </span>
                  <span className="hidden text-xs font-medium text-app-accent opacity-0 transition group-hover:opacity-100 sm:inline">
                    Review
                  </span>
                  <ArrowRight className="h-4 w-4 shrink-0 text-app-faint transition group-hover:translate-x-0.5 group-hover:text-app-accent" />
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <EmptyHint icon={Download} text="No recent games found for this account." />
      )}
    </Surface>
  );
}

function ResultBadge({ outcome }: { outcome: "win" | "loss" | "draw" }) {
  const map = {
    win: { label: "W", cls: "bg-app-good/15 text-app-good ring-app-good/30" },
    loss: { label: "L", cls: "bg-app-loss/15 text-app-loss ring-app-loss/30" },
    draw: { label: "D", cls: "bg-white/5 text-app-muted ring-white/10" },
  }[outcome];
  return (
    <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-md text-xs font-bold ring-1 ring-inset ${map.cls}`}>
      {map.label}
    </span>
  );
}

function CoachNotes({
  className = "",
  insights,
  onPastePgn,
}: {
  className?: string;
  insights: PlayerInsights | null;
  onPastePgn: () => void;
}) {
  const recs = insights?.profile.recommendations ?? [];
  const style = insights?.profile.style;
  return (
    <Surface variant="raised" className={`flex flex-col p-5 ${className}`}>
      <SectionHeading eyebrow="Coach's notes" title={style ? `Your style: ${style}` : "Personalised tips"} />
      {recs.length ? (
        <ul className="mt-1 space-y-3">
          {recs.slice(0, 3).map((rec, i) => (
            <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-app-muted">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-app-accent" />
              <span>{rec}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-sm leading-relaxed text-app-muted">
          Import more games and your coach notes will sharpen — recurring mistakes, openings to review, and what to drill next.
        </p>
      )}
      <button
        onClick={onPastePgn}
        className="mt-auto inline-flex items-center gap-1.5 pt-5 text-xs font-medium text-app-accent hover:text-app-accentHover"
      >
        <FileText className="h-3.5 w-3.5" />
        Analyse another game
      </button>
    </Surface>
  );
}

// ── small shared bits ──────────────────────────────────────────────────────
function Stat({ label, value, tone }: { label: string; value: string; tone?: "blunder" }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-app-subtle">{label}</div>
      <div className={`mt-0.5 nums text-xl font-semibold ${tone === "blunder" ? "text-app-blunder" : "text-app-text"}`}>
        {value}
      </div>
    </div>
  );
}

function Segmented({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="inline-flex rounded-lg border border-app-border bg-app-bgInset p-0.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`rounded-md px-3 py-1 text-xs font-medium transition ${
            value === opt.value ? "bg-app-raised text-app-text shadow-sheen" : "text-app-subtle hover:text-app-text"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function EmptyHint({ icon: Icon, text }: { icon: LucideIcon; text: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 py-8 text-center">
      <Icon className="h-5 w-5 text-app-faint" />
      <p className="text-sm text-app-subtle">{text}</p>
    </div>
  );
}

// ── loading skeleton ─────────────────────────────────────────────────────────
function DashboardSkeleton() {
  return (
    <div className="space-y-7">
      <div className="grid gap-4 lg:grid-cols-12">
        <Skeleton className="h-52 lg:col-span-8" />
        <Skeleton className="h-52 lg:col-span-4" />
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-12">
        <Skeleton className="h-64 lg:col-span-8" />
        <Skeleton className="h-64 lg:col-span-4" />
      </div>
    </div>
  );
}

// ── onboarding (no username) ────────────────────────────────────────────────
function Onboarding({
  apiStatus,
  onUsernameChange,
  onPastePgn,
  onTrySample,
  sampleLoading,
}: HomeDashboardProps) {
  const [draft, setDraft] = useState("");

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onUsernameChange(draft.trim());
  }

  const features: { icon: LucideIcon; title: string; text: string }[] = [
    { icon: BarChart3, title: "Player insights", text: "Accuracy, recurring mistakes, and trends over time." },
    { icon: BookOpen, title: "Opening repertoire", text: "Which openings you play and how they score." },
    { icon: Puzzle, title: "Personal puzzles", text: "Tactics drawn from your own blunders." },
  ];

  return (
    <div className="mx-auto w-full max-w-3xl animate-rise pb-12 pt-6">
      <div className="mb-6 flex justify-center">
        <ApiStatusIndicator status={apiStatus} />
      </div>
      <Surface variant="raised" className="relative overflow-hidden p-8 text-center sm:p-10">
        <div className="pointer-events-none absolute -right-10 -top-12 text-[200px] leading-none text-app-accent/[0.05]">
          <ChessGlyph piece="knight" />
        </div>
        <span className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-2xl border border-app-accentLine bg-accent-sheen text-3xl text-app-accent shadow-sheen">
          <ChessGlyph piece="knight" />
        </span>
        <h1 className="text-3xl font-semibold tracking-tightest text-app-text">A serious home for your chess.</h1>
        <p className="mx-auto mt-3 max-w-md text-[15px] leading-relaxed text-app-muted">
          Connect your Chess.com account to unlock accuracy trends, an opening repertoire, and tactics built from your own games.
        </p>
        <form className="mx-auto mt-7 flex max-w-md flex-col gap-2.5 sm:flex-row" onSubmit={submit}>
          <input
            className="h-12 flex-1 rounded-xl border border-app-border bg-app-bgInset px-4 text-app-text outline-none transition placeholder:text-app-faint focus:border-app-accentLine focus-visible:ring-2 focus-visible:ring-app-accent/40"
            value={draft}
            placeholder="Your Chess.com username"
            aria-label="Chess.com username"
            autoComplete="username"
            onChange={(e) => setDraft(e.target.value)}
          />
          <Button variant="primary" size="lg" type="submit" disabled={!draft.trim()}>
            Continue
            <ArrowRight className="h-4 w-4" />
          </Button>
        </form>
        <p className="mt-3 text-xs text-app-faint">We only read your public games — no password required.</p>

        <div className="mt-8 grid gap-3 border-t border-app-border pt-7 sm:grid-cols-3">
          {features.map((f) => {
            const Icon = f.icon;
            return (
              <div key={f.title} className="rounded-xl border border-app-border bg-app-bgInset/60 p-4 text-left">
                <Icon className="h-5 w-5 text-app-accent" strokeWidth={2} />
                <h3 className="mt-3 text-sm font-semibold text-app-text">{f.title}</h3>
                <p className="mt-1 text-xs leading-relaxed text-app-muted">{f.text}</p>
              </div>
            );
          })}
        </div>

        <div className="mt-7 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-sm">
          <span className="text-app-muted">No account?</span>
          <button onClick={onPastePgn} className="font-medium text-app-text underline-offset-4 hover:text-app-accent hover:underline">
            Paste a PGN
          </button>
          <span className="text-app-faint">or</span>
          <button
            onClick={onTrySample}
            disabled={sampleLoading}
            className="inline-flex items-center gap-1.5 font-medium text-app-accent hover:text-app-accentHover disabled:opacity-70"
          >
            {sampleLoading ? (
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-app-accent/40 border-t-app-accent" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            try {SAMPLE_GAME_LABEL}
          </button>
        </div>
      </Surface>
    </div>
  );
}
