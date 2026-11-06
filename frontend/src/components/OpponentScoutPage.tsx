import { Chess } from "chess.js";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Chessboard } from "react-chessboard";
import {
  AlertTriangle,
  ArrowUpRight,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  Crosshair,
  Cpu,
  FlipVertical2,
  Hourglass,
  Search,
  ShieldAlert,
  Swords,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";
import { apiErrorMessage, fetchScoutingReport } from "../api/client";
import type {
  ScoutDecisionPoint,
  ScoutFamilyRow,
  ScoutLine,
  ScoutMoveRow,
  ScoutStats,
  ScoutTimeClass,
  ScoutTreeNode,
  ScoutingReport,
} from "../types";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";
import { Delta } from "./ui/Delta";
import { StatCard } from "./ui/StatCard";
import { WinLossBar } from "./ui/WinLossBar";

interface OpponentScoutPageProps {
  /** The signed-in Chess.com username, used for the matchup section. */
  myUsername: string;
}

type Side = "white" | "black"; // the *opponent's* colour

const LAST_OPPONENT_KEY = "cr_scout_opponent";

const input =
  "h-11 w-full rounded-lg border border-app-border bg-app-panelSecondary px-3 text-sm text-app-text outline-none transition placeholder:text-app-muted focus-visible:border-app-accent focus-visible:ring-2 focus-visible:ring-app-accent/50";

function readStorage(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function pct(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? "–" : `${value.toFixed(digits)}%`;
}

function evalText(cp: number | null | undefined): string {
  if (cp === null || cp === undefined) return "–";
  const pawns = cp / 100;
  return `${pawns > 0 ? "+" : ""}${pawns.toFixed(1)}`;
}

function evalTone(cp: number | null | undefined): string {
  if (cp === null || cp === undefined) return "text-app-faint";
  // Their POV: negative is good for you.
  if (cp <= -50) return "text-app-good";
  if (cp >= 50) return "text-app-blunder";
  return "text-app-muted";
}

/** SAN path -> "1. e4 c6 2. d4" style text. */
function lineText(path: string[]): string {
  return path
    .map((san, i) => (i % 2 === 0 ? `${i / 2 + 1}. ${san}` : san))
    .join(" ");
}

function moveLabel(ply: number, san: string): string {
  // ``ply`` is the ply *after* the move (1 = White's first move).
  const moveNo = Math.ceil(ply / 2);
  return ply % 2 === 1 ? `${moveNo}. ${san}` : `${moveNo}… ${san}`;
}

function findNode(root: ScoutTreeNode, path: string[]): { node: ScoutTreeNode; path: string[] } {
  let node = root;
  const walked: string[] = [];
  for (const san of path) {
    const next = node.children.find((child) => child.san === san);
    if (!next) break;
    node = next;
    walked.push(san);
  }
  return { node, path: walked };
}

function lastMoveSquares(path: string[]): Record<string, React.CSSProperties> {
  if (!path.length) return {};
  const chess = new Chess();
  let from = "";
  let to = "";
  try {
    for (const san of path) {
      const move = chess.move(san);
      from = move.from;
      to = move.to;
    }
  } catch {
    return {};
  }
  const style = { backgroundColor: "rgba(200,161,90,0.38)" };
  return { [from]: style, [to]: style };
}

/** Score cell: their score, coloured by how it compares with rating expectation. */
function ScoreCell({ stats }: { stats: Pick<ScoutStats, "score_pct" | "expected_pct" | "perf_delta" | "games"> }) {
  return (
    <div className="flex flex-col items-end gap-0.5">
      <span className="nums text-sm font-semibold text-app-text">{pct(stats.score_pct)}</span>
      {stats.expected_pct !== null && (
        <span className="nums text-[11px] text-app-faint">exp {pct(stats.expected_pct)}</span>
      )}
    </div>
  );
}

function PerfDelta({ value }: { value: number | null | undefined }) {
  // Negative = they underperform their rating = good for you, so invert colours.
  return <Delta value={value ?? null} suffix="" invert decimals={0} />;
}

function ConfidenceDot({ games }: { games: number }) {
  const tone = games >= 12 ? "bg-app-good" : games >= 5 ? "bg-app-warning" : "bg-app-faint";
  const label = games >= 12 ? "High confidence" : games >= 5 ? "Medium confidence" : "Small sample";
  return <span title={label} className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${tone}`} />;
}

function FamiliarityMeter({ score, label }: { score: number; label: string }) {
  const tone = score >= 70 ? "bg-app-blunder" : score >= 45 ? "bg-app-mistake" : score >= 25 ? "bg-app-warning" : "bg-app-good";
  return (
    <div className="min-w-[110px]">
      <div className="flex items-center justify-between text-[11px]">
        <span className="font-medium text-app-muted">{label}</span>
        <span className="nums text-app-faint">{score}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.max(4, score)}%` }} />
      </div>
    </div>
  );
}

function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: Array<{ value: T; label: string }>;
  onChange: (value: T) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-app-border bg-app-panelSecondary p-1">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`h-8 rounded-md px-3 text-sm font-medium transition ${
            value === option.value ? "bg-app-raisedHover text-app-text shadow-sheen" : "text-app-muted hover:text-app-text"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export function OpponentScoutPage({ myUsername }: OpponentScoutPageProps) {
  const [opponent, setOpponent] = useState(() => readStorage(LAST_OPPONENT_KEY));
  const [limit, setLimit] = useState(300);
  const [timeClass, setTimeClass] = useState<ScoutTimeClass>("");
  const [ratedOnly, setRatedOnly] = useState(false);
  const [engine, setEngine] = useState(true);
  const [compare, setCompare] = useState(true);
  const [report, setReport] = useState<ScoutingReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [side, setSide] = useState<Side>("black");
  const [path, setPath] = useState<string[]>([]);
  const explorerRef = useRef<HTMLDivElement | null>(null);

  const me = myUsername.trim();
  const sameAsMe = me && opponent.trim().toLowerCase() === me.toLowerCase();

  async function runScout() {
    const name = opponent.trim();
    if (!name) return;
    setLoading(true);
    setError(null);
    try {
      localStorage.setItem(LAST_OPPONENT_KEY, name);
    } catch {
      /* storage unavailable: fine */
    }
    try {
      const result = await fetchScoutingReport(name, {
        limit,
        time_class: timeClass,
        rated_only: ratedOnly,
        engine,
        me: compare && me && !sameAsMe ? me : undefined,
      });
      setReport(result);
      setPath([]);
      // Start the explorer on the side you'll most likely need: their more-played colour.
      setSide(result.profile.black.games >= result.profile.white.games ? "black" : "white");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function openLine(color: Side, linePath: string[]) {
    setSide(color);
    setPath(linePath);
    explorerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <div className="grid animate-fade-in gap-5">
      <Card>
        <CardHeader title="Scout an opponent" eyebrow="Opening preparation">
          Read an opponent's public Chess.com games: what they play, what they know deeply, and where they score below
          their rating.
        </CardHeader>
        <form
          className="grid gap-3 lg:grid-cols-[1fr_120px_160px_auto] lg:items-center"
          onSubmit={(event) => {
            event.preventDefault();
            void runScout();
          }}
        >
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-app-faint" />
            <input
              className={`${input} pl-9`}
              value={opponent}
              placeholder="Opponent's Chess.com username"
              onChange={(event) => setOpponent(event.target.value)}
              aria-label="Opponent username"
            />
          </div>
          <select className={input} value={limit} onChange={(event) => setLimit(Number(event.target.value))} aria-label="Games to read">
            {[100, 200, 300, 500].map((n) => (
              <option key={n} value={n}>
                {n} games
              </option>
            ))}
          </select>
          <select
            className={input}
            value={timeClass}
            onChange={(event) => setTimeClass(event.target.value as ScoutTimeClass)}
            aria-label="Time control"
          >
            <option value="">All time controls</option>
            <option value="bullet">Bullet</option>
            <option value="blitz">Blitz</option>
            <option value="rapid">Rapid</option>
            <option value="daily">Daily</option>
          </select>
          <Button variant="primary" type="submit" disabled={!opponent.trim() || loading}>
            <Crosshair className="h-4 w-4" />
            {loading ? "Scouting…" : "Scout"}
          </Button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          <Toggle checked={ratedOnly} onChange={setRatedOnly} label="Rated only" />
          <Toggle
            checked={engine}
            onChange={setEngine}
            label="Engine check"
            hint="Stockfish scores where each game stands after move 12 (adds ~5–15s)"
          />
          <Toggle
            checked={compare && !!me && !sameAsMe}
            disabled={!me || !!sameAsMe}
            onChange={setCompare}
            label={me ? `Compare with ${me}` : "Compare with my games"}
            hint={me ? "Cross their weak spots with the openings you actually play" : "Set your username on the dashboard first"}
          />
        </div>
      </Card>

      {error && (
        <div className="flex items-start gap-3 rounded-lg bg-app-blunder/10 px-4 py-3 text-sm text-app-blunder ring-1 ring-app-blunder/30">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!report ? (
        <Card>
          <div className="flex flex-col items-center gap-3 py-16 text-center">
            <div className="grid h-11 w-11 place-items-center rounded-full bg-app-panelSecondary text-app-muted">
              <Crosshair className="h-5 w-5" />
            </div>
            <p className="max-w-md text-sm text-app-muted">
              {loading
                ? "Reading their games, building the opening tree" + (engine ? " and checking positions with Stockfish…" : "…")
                : "Enter your next opponent's username to see their repertoire, how well they know each line, and where to take the game."}
            </p>
          </div>
        </Card>
      ) : report.profile.games === 0 ? (
        <Card>
          <p className="py-10 text-center text-sm text-app-muted">
            No standard games found for {report.username} with these filters.
          </p>
        </Card>
      ) : (
        <>
          <ProfileStrip report={report} />
          <GamePlan report={report} />
          <div ref={explorerRef} className="scroll-mt-6">
            <Explorer report={report} side={side} onSideChange={(s) => { setSide(s); setPath([]); }} path={path} onPathChange={setPath} />
          </div>
          <KeyLines report={report} onOpen={openLine} />
          <Repertoire report={report} onOpen={openLine} />
          <Habits report={report} />
          {report.matchup && <Matchup report={report} />}
          <Methodology report={report} />
        </>
      )}
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  label,
  hint,
  disabled = false,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  hint?: string;
  disabled?: boolean;
}) {
  return (
    <label
      title={hint}
      className={`flex h-9 items-center gap-2 rounded-lg border border-app-border bg-app-panelSecondary px-3 text-sm transition ${
        disabled ? "cursor-not-allowed text-app-faint" : "cursor-pointer text-app-muted hover:bg-app-panelHover"
      }`}
    >
      <input
        type="checkbox"
        className="h-4 w-4 accent-app-accent"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  );
}

// ── profile ───────────────────────────────────────────────────────────────────

function ProfileStrip({ report }: { report: ScoutingReport }) {
  const p = report.profile;
  const ratings = Object.entries(p.ratings);
  const losses = p.terminations.loss.reduce((sum, row) => sum + row.games, 0);
  const timeLosses = p.terminations.loss.find((row) => row.reason === "time")?.games ?? 0;
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <h2 className="font-mono text-xl font-semibold text-app-text">{report.username}</h2>
        {ratings.map(([tc, rating]) => (
          <Badge key={tc} tone="neutral">{`${tc} ${rating}`}</Badge>
        ))}
        <span className="text-xs text-app-faint">
          {p.games} games · avg {p.avg_game_length?.toFixed(0) ?? "–"} moves
          {report.engine.enabled &&
            (report.engine.available
              ? ` · ${report.engine.evaluated_games} positions engine-checked`
              : " · engine check unavailable")}
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Score vs rating"
          value={pct(p.overall.score_pct)}
          icon={TrendingUp}
          caption={`expected ${pct(p.overall.expected_pct)}`}
          delta={p.overall.perf_delta}
          invertDelta
        />
        <StatCard
          label="As White"
          value={pct(p.white.score_pct)}
          icon={Swords}
          caption={`${p.white.games} games`}
          delta={p.white.perf_delta}
          invertDelta
        />
        <StatCard
          label="As Black"
          value={pct(p.black.score_pct)}
          icon={ShieldAlert}
          caption={`${p.black.games} games`}
          delta={p.black.perf_delta}
          invertDelta
        />
        <StatCard
          label="Losses on time"
          value={losses ? pct((timeLosses / losses) * 100) : "–"}
          icon={Hourglass}
          caption={`${timeLosses} of ${losses} losses`}
        />
      </div>
    </div>
  );
}

// ── game plan ─────────────────────────────────────────────────────────────────

function GamePlan({ report }: { report: ScoutingReport }) {
  const plan = report.game_plan;
  const columns: Array<{ title: string; items: string[]; icon: ReactNode }> = [
    { title: "When you have White", items: plan.you_white, icon: <span className="h-3 w-3 rounded-full bg-[#f0d9b5]" /> },
    { title: "When you have Black", items: plan.you_black, icon: <span className="h-3 w-3 rounded-full bg-[#3a3a40] ring-1 ring-white/20" /> },
    { title: "Habits to exploit", items: plan.general, icon: <Target className="h-3.5 w-3.5 text-app-accent" /> },
  ];
  return (
    <Card>
      <CardHeader title="Game plan" eyebrow={`Against ${report.username}`}>
        Takeaways from their results, adjusted for the ratings they faced.
      </CardHeader>
      <div className="grid gap-4 lg:grid-cols-3">
        {columns.map((col) => (
          <div key={col.title} className="rounded-xl border border-app-border bg-app-raised/50 p-4">
            <div className="mb-3 flex items-center gap-2">
              {col.icon}
              <h3 className="text-sm font-semibold text-app-text">{col.title}</h3>
            </div>
            {col.items.length ? (
              <ul className="grid gap-2.5">
                {col.items.map((item) => (
                  <li key={item} className="flex gap-2 text-sm leading-relaxed text-app-muted">
                    <ChevronRight className="mt-1 h-3.5 w-3.5 shrink-0 text-app-accent/70" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-app-faint">Not enough games for a clear signal.</p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── explorer ──────────────────────────────────────────────────────────────────

function Explorer({
  report,
  side,
  onSideChange,
  path,
  onPathChange,
}: {
  report: ScoutingReport;
  side: Side;
  onSideChange: (side: Side) => void;
  path: string[];
  onPathChange: (path: string[]) => void;
}) {
  const root = report.tree[side];
  const { node, path: walked } = useMemo(() => findNode(root, path), [root, path]);
  const [flipped, setFlipped] = useState(false);
  const orientation: Side = (side === "black") !== flipped ? "white" : "black";
  const squares = useMemo(() => lastMoveSquares(walked), [walked]);
  const baselineTime = report.baseline.avg_move_time_pct;
  const theyToMove = node.children[0]?.by === "them";

  useEffect(() => setFlipped(false), [side]);

  return (
    <Card>
      <CardHeader
        title="Opening explorer"
        eyebrow="Their games, move by move"
        action={
          <Segmented<Side>
            value={side}
            onChange={onSideChange}
            options={[
              { value: "black", label: `They're Black (${report.profile.black.games})` },
              { value: "white", label: `They're White (${report.profile.white.games})` },
            ]}
          />
        }
      >
        Scores are theirs; green means they do worse than their rating predicts.
      </CardHeader>

      <div className="grid gap-5 lg:grid-cols-[minmax(280px,420px)_1fr]">
        <div>
          <div className="overflow-hidden rounded-lg border border-app-border">
            <Chessboard
              id="scout-board"
              position={node.fen}
              boardOrientation={orientation}
              arePiecesDraggable={false}
              animationDuration={150}
              customSquareStyles={squares}
              customDarkSquareStyle={{ backgroundColor: "#b58863" }}
              customLightSquareStyle={{ backgroundColor: "#f0d9b5" }}
            />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button variant="control" size="sm" onClick={() => onPathChange(walked.slice(0, -1))} disabled={!walked.length}>
              <ChevronLeft className="h-4 w-4" />
              Back
            </Button>
            <Button variant="ghost" size="sm" onClick={() => onPathChange([])} disabled={!walked.length}>
              Start
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setFlipped((f) => !f)}>
              <FlipVertical2 className="h-4 w-4" />
              Flip
            </Button>
          </div>
        </div>

        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center gap-1 rounded-lg bg-app-panelSecondary px-3 py-2 font-mono text-xs text-app-muted">
            {walked.length === 0 ? (
              <span>Starting position</span>
            ) : (
              walked.map((san, i) => (
                <button
                  key={`${i}-${san}`}
                  type="button"
                  onClick={() => onPathChange(walked.slice(0, i + 1))}
                  className="rounded px-1 py-0.5 hover:bg-app-raisedHover hover:text-app-text"
                >
                  {i % 2 === 0 ? `${i / 2 + 1}. ${san}` : san}
                </button>
              ))
            )}
          </div>

          <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-app-muted">
            <span>
              <span className="nums font-semibold text-app-text">{node.games}</span> games here
            </span>
            <span>
              they score <span className="nums font-semibold text-app-text">{pct(node.score_pct)}</span>
              {node.expected_pct !== null && <> (exp {pct(node.expected_pct)})</>}
            </span>
            {node.avg_eval_cp !== null && (
              <span>
                eval at move 12 <span className={`nums font-semibold ${evalTone(node.avg_eval_cp)}`}>{evalText(node.avg_eval_cp)}</span>
              </span>
            )}
          </div>

          {node.children.length ? (
            <>
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-app-subtle">
                {theyToMove ? "What they play here" : "What their opponents tried"}
              </p>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-wider text-app-faint">
                      <th className="pb-2 font-medium">Move</th>
                      <th className="pb-2 font-medium">Played</th>
                      <th className="pb-2 text-right font-medium">Their score</th>
                      <th className="pb-2 text-right font-medium">vs rating</th>
                      <th className="pb-2 text-right font-medium" title="Average engine eval after move 12, their point of view">
                        Eval@12
                      </th>
                      {theyToMove && (
                        <th className="pb-2 text-right font-medium" title="Share of their starting clock spent on this move">
                          Clock
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {node.children.map((child) => {
                      const slow =
                        theyToMove && child.avg_time_pct !== null && baselineTime !== null && child.avg_time_pct >= Math.max(1.5, baselineTime * 2.5);
                      return (
                        <tr
                          key={child.san}
                          onClick={() => onPathChange([...walked, child.san ?? ""])}
                          className="cursor-pointer border-t border-app-border/60 transition hover:bg-app-raised"
                        >
                          <td className="py-2 pr-2">
                            <div className="flex items-center gap-2">
                              <ConfidenceDot games={child.games} />
                              <span className="font-mono font-medium text-app-text">{moveLabel(child.ply, child.san ?? "")}</span>
                            </div>
                          </td>
                          <td className="py-2 pr-3">
                            <div className="flex items-center gap-2">
                              <div className="h-1.5 w-20 overflow-hidden rounded-full bg-white/5">
                                <div className="h-full rounded-full bg-app-accent/70" style={{ width: `${child.frequency ?? 0}%` }} />
                              </div>
                              <span className="nums text-xs text-app-muted">
                                {child.games} · {pct(child.frequency)}
                              </span>
                            </div>
                          </td>
                          <td className="py-2 text-right">
                            <ScoreCell stats={child} />
                          </td>
                          <td className="py-2 text-right">
                            <PerfDelta value={child.perf_delta} />
                          </td>
                          <td className={`nums py-2 text-right font-mono text-xs ${evalTone(child.avg_eval_cp)}`}>
                            {evalText(child.avg_eval_cp)}
                          </td>
                          {theyToMove && (
                            <td className={`nums py-2 text-right text-xs ${slow ? "font-semibold text-app-warning" : "text-app-muted"}`}>
                              {child.avg_time_pct !== null ? `${child.avg_time_pct.toFixed(1)}%` : "–"}
                              {slow && <Clock className="ml-1 inline h-3 w-3" />}
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="rounded-lg border border-dashed border-app-border px-4 py-6 text-center text-sm text-app-faint">
              Their games split up after this point — fewer than two games share any next move.
            </p>
          )}
        </div>
      </div>
    </Card>
  );
}

// ── key lines ─────────────────────────────────────────────────────────────────

function KeyLines({ report, onOpen }: { report: ScoutingReport; onOpen: (side: Side, path: string[]) => void }) {
  return (
    <div className="grid gap-5 xl:grid-cols-3">
      <LineList
        title="Steer into"
        eyebrow="They underperform here"
        empty="No line with enough games where they clearly underperform."
        lines={report.steer_into}
        tone="good"
        onOpen={onOpen}
      />
      <LineList
        title="Avoid"
        eyebrow="Their home turf"
        empty="No line where they clearly overperform."
        lines={report.avoid}
        tone="bad"
        onOpen={onOpen}
      />
      <DecisionList points={report.decision_points} onOpen={onOpen} />
    </div>
  );
}

function sideTag(color: Side) {
  return color === "black" ? "You: White" : "You: Black";
}

function LineList({
  title,
  eyebrow,
  empty,
  lines,
  tone,
  onOpen,
}: {
  title: string;
  eyebrow: string;
  empty: string;
  lines: ScoutLine[];
  tone: "good" | "bad";
  onOpen: (side: Side, path: string[]) => void;
}) {
  return (
    <Card>
      <CardHeader title={title} eyebrow={eyebrow} />
      {lines.length ? (
        <ul className="grid gap-2">
          {lines.map((line) => (
            <li key={`${line.opponent_color}-${line.line}`}>
              <button
                type="button"
                onClick={() => onOpen(line.opponent_color, line.path)}
                className="group w-full rounded-lg border border-app-border bg-app-raised/50 px-3 py-2.5 text-left transition hover:border-app-borderStrong hover:bg-app-raised"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-mono text-[13px] font-medium text-app-text">{line.line}</span>
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-app-faint group-hover:text-app-accent" />
                </div>
                <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-app-muted">
                  <Badge tone="neutral">{sideTag(line.opponent_color)}</Badge>
                  <span className="nums">{line.games} games</span>
                  <span className={`nums font-semibold ${tone === "good" ? "text-app-good" : "text-app-blunder"}`}>
                    they score {pct(line.score_pct)}
                  </span>
                  {line.expected_pct !== null && <span className="nums text-app-faint">exp {pct(line.expected_pct)}</span>}
                  {line.avg_eval_cp !== null && (
                    <span className={`nums font-mono ${evalTone(line.avg_eval_cp)}`}>@12 {evalText(line.avg_eval_cp)}</span>
                  )}
                </div>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-app-faint">{empty}</p>
      )}
    </Card>
  );
}

function DecisionList({ points, onOpen }: { points: ScoutDecisionPoint[]; onOpen: (side: Side, path: string[]) => void }) {
  return (
    <Card>
      <CardHeader title="Where they get unsure" eyebrow="Prep runs out" />
      {points.length ? (
        <ul className="grid gap-2">
          {points.map((point) => (
            <li key={`${point.opponent_color}-${point.line}`}>
              <button
                type="button"
                onClick={() => onOpen(point.opponent_color, point.path)}
                className="group w-full rounded-lg border border-app-border bg-app-raised/50 px-3 py-2.5 text-left transition hover:border-app-borderStrong hover:bg-app-raised"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-mono text-[13px] font-medium text-app-text">{point.line}</span>
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-app-faint group-hover:text-app-accent" />
                </div>
                <p className="mt-1 text-xs leading-relaxed text-app-muted">{point.reason}</p>
                <p className="mt-1 font-mono text-[11px] text-app-faint">
                  {point.replies.map((r) => `${r.san} ×${r.games}`).join(" · ")}
                </p>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-app-faint">They answer consistently and at normal speed in every well-sampled position.</p>
      )}
    </Card>
  );
}

// ── repertoire ────────────────────────────────────────────────────────────────

function Repertoire({ report, onOpen }: { report: ScoutingReport; onOpen: (side: Side, path: string[]) => void }) {
  const [side, setSide] = useState<Side>(report.profile.black.games >= report.profile.white.games ? "black" : "white");
  const families = report.families[side];
  const moveRows = side === "white" ? report.as_white.first_moves : report.as_black.vs_first_moves;
  return (
    <Card>
      <CardHeader
        title="Repertoire & familiarity"
        eyebrow="What they know"
        action={
          <Segmented<Side>
            value={side}
            onChange={setSide}
            options={[
              { value: "black", label: "As Black" },
              { value: "white", label: "As White" },
            ]}
          />
        }
      >
        Familiarity blends how often they play a line, how deep they follow their own move order, and how fast they play
        its first ten moves.
      </CardHeader>

      <FirstMoves rows={moveRows} side={side} />

      <div className="mt-5 grid gap-2">
        {families.map((row) => (
          <FamilyRow key={row.family} row={row} side={side} onOpen={onOpen} />
        ))}
      </div>
    </Card>
  );
}

function FirstMoves({ rows, side }: { rows: ScoutMoveRow[]; side: Side }) {
  const shown = rows.slice(0, 5);
  if (!shown.length) return null;
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {shown.map((row) => (
        <div key={row.move} className="rounded-xl border border-app-border bg-app-raised/50 p-4">
          <div className="flex items-center justify-between">
            <span className="font-mono text-sm font-semibold text-app-text">
              {side === "white" ? `They open 1. ${row.move}` : `vs 1. ${row.move}`}
            </span>
            <span className="nums text-xs text-app-muted">
              {row.games} · {pct(row.frequency)}
            </span>
          </div>
          <div className="mt-2 flex items-center justify-between gap-2">
            <WinLossBar wins={row.wins} draws={row.draws} losses={row.losses} className="flex-1" />
            <span className="nums text-xs font-semibold text-app-text">{pct(row.score_pct)}</span>
            <PerfDelta value={row.perf_delta} />
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {row.replies.slice(0, 5).map((reply) => (
              <span
                key={reply.move}
                title={`${reply.games} games · they score ${pct(reply.score_pct)}`}
                className={`rounded-md px-1.5 py-0.5 font-mono text-[11px] ring-1 ring-inset ${
                  reply.games >= 3 && reply.shrunk_delta <= -4
                    ? "bg-app-good/10 text-app-good ring-app-good/30"
                    : reply.games >= 3 && reply.shrunk_delta >= 4
                      ? "bg-app-blunder/10 text-app-blunder ring-app-blunder/30"
                      : "bg-app-panelSecondary text-app-muted ring-app-border"
                }`}
              >
                {side === "white" ? `1… ${reply.move}` : reply.move} {pct(reply.frequency)}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function FamilyRow({ row, side, onOpen }: { row: ScoutFamilyRow; side: Side; onOpen: (side: Side, path: string[]) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-app-border bg-app-raised/40">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="grid w-full grid-cols-[1fr_auto] items-center gap-3 px-4 py-3 text-left sm:grid-cols-[minmax(0,1.6fr)_120px_70px_60px_80px_20px]"
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ConfidenceDot games={row.games} />
            <span className="truncate text-sm font-semibold text-app-text">{row.family}</span>
            <span className="hidden text-[11px] text-app-faint sm:inline">{row.eco}</span>
          </div>
          <span className="nums text-xs text-app-muted">
            {row.games} games · {pct(row.frequency)} of their {side} games
          </span>
        </div>
        <div className="hidden sm:block">
          <FamiliarityMeter score={row.familiarity.score} label={row.familiarity.label} />
        </div>
        <div className="hidden text-right sm:block">
          <ScoreCell stats={row} />
        </div>
        <div className="hidden text-right sm:block">
          <PerfDelta value={row.perf_delta} />
        </div>
        <div className={`hidden text-right font-mono text-xs sm:block ${evalTone(row.avg_eval_cp)}`} title="Avg eval after move 12 (their POV)">
          {evalText(row.avg_eval_cp)}
        </div>
        <ChevronDown className={`h-4 w-4 text-app-faint transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="grid gap-4 border-t border-app-border px-4 py-4 lg:grid-cols-2">
          <div className="grid content-start gap-3">
            <div className="sm:hidden">
              <FamiliarityMeter score={row.familiarity.score} label={row.familiarity.label} />
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <MiniStat label="Volume" value={`${row.familiarity.components.volume}`} />
              <MiniStat label="Book depth" value={row.avg_book_depth !== null ? `${row.avg_book_depth.toFixed(1)} mv` : "–"} />
              <MiniStat label="Clock by mv 10" value={pct(row.avg_opening_time_pct, 1)} />
              <MiniStat label="First long think" value={row.avg_first_think !== null ? `move ${row.avg_first_think.toFixed(0)}` : "–"} />
              <MiniStat label="Early losses" value={pct(row.early_loss_rate)} />
              <MiniStat label="Accuracy" value={row.avg_accuracy !== null ? row.avg_accuracy.toFixed(0) : "–"} />
            </div>
            {row.main_line && (
              <button
                type="button"
                onClick={() => onOpen(side, row.main_line_path)}
                className="group rounded-lg bg-app-panelSecondary px-3 py-2 text-left"
              >
                <span className="text-[11px] font-semibold uppercase tracking-wider text-app-subtle">
                  Their usual move order ({row.main_line_games} games all the way)
                </span>
                <span className="mt-1 block font-mono text-xs text-app-text group-hover:text-app-accent">{row.main_line}</span>
              </button>
            )}
          </div>
          <div className="grid content-start gap-3">
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-app-subtle">Variations</p>
              <table className="w-full text-xs">
                <tbody>
                  {row.variations.map((v) => (
                    <tr key={v.variation} className="border-t border-app-border/60">
                      <td className="py-1.5 pr-2 text-app-text">{v.variation}</td>
                      <td className="nums py-1.5 text-right text-app-muted">{v.games}</td>
                      <td className="nums py-1.5 text-right font-semibold text-app-text">{pct(v.score_pct)}</td>
                      <td className="py-1.5 text-right">
                        <PerfDelta value={v.perf_delta} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-app-subtle">Recent games</p>
              <ul className="grid gap-1">
                {row.recent_games.map((g, i) => (
                  <li key={`${g.url}-${i}`} className="flex items-center justify-between gap-2 text-xs">
                    <span className="truncate text-app-muted">
                      <span
                        className={`mr-1.5 inline-block w-8 font-semibold ${
                          g.result === "win" ? "text-app-blunder" : g.result === "loss" ? "text-app-good" : "text-app-draw"
                        }`}
                      >
                        {g.result === "win" ? "Won" : g.result === "loss" ? "Lost" : "Drew"}
                      </span>
                      vs {g.foe} {g.foe_rating ? `(${g.foe_rating})` : ""} · {g.variation ?? "main line"}
                    </span>
                    {g.url && (
                      <a href={g.url} target="_blank" rel="noreferrer" className="shrink-0 text-app-faint hover:text-app-accent">
                        {g.date}
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-app-panelSecondary px-2 py-2">
      <div className="nums text-sm font-semibold text-app-text">{value}</div>
      <div className="mt-0.5 text-[10px] uppercase tracking-wider text-app-faint">{label}</div>
    </div>
  );
}

// ── habits ────────────────────────────────────────────────────────────────────

const REASON_LABEL: Record<string, string> = {
  resignation: "Resigned",
  checkmate: "Checkmated",
  time: "Lost on time",
  abandoned: "Abandoned",
  other: "Other",
};

function Habits({ report }: { report: ScoutingReport }) {
  const p = report.profile;
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <Card>
        <CardHeader title="How they lose" eyebrow="Endings" />
        {p.terminations.loss.length ? (
          <ul className="grid gap-2.5">
            {p.terminations.loss.map((row) => (
              <li key={row.reason}>
                <div className="flex justify-between text-sm">
                  <span className="text-app-muted">{REASON_LABEL[row.reason] ?? row.reason}</span>
                  <span className="nums text-app-text">
                    {row.games} · {pct(row.pct)}
                  </span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/5">
                  <div className="h-full rounded-full bg-app-good/70" style={{ width: `${row.pct}%` }} />
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-app-faint">No losses in this sample.</p>
        )}
        <p className="mt-4 text-xs text-app-muted">
          Early collapses (lost within 25 moves): <span className="nums font-semibold text-app-text">{pct(p.overall.early_loss_rate)}</span>{" "}
          of games.
        </p>
      </Card>

      <Card>
        <CardHeader title="Game length" eyebrow="Stamina" />
        <div className="grid gap-3">
          {[
            { label: "Up to move 40", stats: p.short_games },
            { label: "Past move 40", stats: p.long_games },
          ].map(({ label, stats }) => (
            <div key={label}>
              <div className="flex items-center justify-between text-sm">
                <span className="text-app-muted">{label}</span>
                <span className="flex items-center gap-2">
                  <span className="nums text-xs text-app-faint">{stats.games} games</span>
                  <span className="nums font-semibold text-app-text">{pct(stats.score_pct)}</span>
                  <PerfDelta value={stats.perf_delta} />
                </span>
              </div>
              <WinLossBar wins={stats.wins} draws={stats.draws} losses={stats.losses} className="mt-1.5" />
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="Clock & trends" eyebrow="Tendencies" />
        <div className="grid gap-2 text-sm">
          <p className="text-app-muted">
            <Clock className="mr-1.5 inline h-3.5 w-3.5 text-app-faint" />
            Uses <span className="nums font-semibold text-app-text">{pct(report.baseline.avg_opening_time_pct, 1)}</span> of their clock by
            move 10 on average
            {p.overall.avg_first_think !== null && (
              <>
                ; first long think around move <span className="nums font-semibold text-app-text">{p.overall.avg_first_think.toFixed(0)}</span>
              </>
            )}
            .
          </p>
          {report.recent_changes.length ? (
            <ul className="mt-1 grid gap-1.5">
              {report.recent_changes.map((change) => (
                <li key={`${change.color}-${change.family}-${change.direction}`} className="flex items-center gap-2 text-xs">
                  <Badge tone={change.direction === "new" ? "yellow" : "neutral"}>{change.direction === "new" ? "New" : "Dropped"}</Badge>
                  <span className="text-app-muted">
                    {change.family} as {change.color}: {pct(change.earlier_share)} → {pct(change.recent_share)}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-app-faint">No recent change in their opening choices.</p>
          )}
        </div>
      </Card>
    </div>
  );
}

// ── matchup ───────────────────────────────────────────────────────────────────

function Matchup({ report }: { report: ScoutingReport }) {
  const m = report.matchup!;
  return (
    <Card>
      <CardHeader title={`${m.username} vs ${report.username}`} eyebrow="Your repertoire against theirs">
        Your results in the lines they actually go for, plus how they do against each choice. Edge = your score above 50%
        minus their rating-adjusted over-performance, with small samples pulled toward even.
      </CardHeader>
      <div className="grid gap-5 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-app-text">
            <Users className="h-4 w-4 text-app-faint" /> You with White
          </h3>
          {m.you_white.length ? (
            <div className="grid gap-2">
              {m.you_white.map((row, i) => (
                <div key={row.move} className={`rounded-lg border px-3 py-2.5 ${i === 0 ? "border-app-accentLine bg-app-accentSoft" : "border-app-border bg-app-raised/50"}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm font-semibold text-app-text">1. {row.move}</span>
                    <span className="flex items-center gap-2 text-xs">
                      <span className="text-app-muted">edge</span>
                      <Delta value={row.edge} decimals={0} />
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-app-muted">
                    You {pct(row.your_score_pct)} in {row.your_games} · they {row.their_games ? `${pct(row.their_score_pct)} in ${row.their_games}` : "have never faced it"}
                  </p>
                  {row.likely_lines.length > 0 && (
                    <p className="mt-1 text-[11px] text-app-faint">
                      They answer with:{" "}
                      {row.likely_lines
                        .map((l) => `${l.family} ${pct(l.their_share)}${l.your_score_pct !== null ? ` (you ${pct(l.your_score_pct)})` : ""}`)
                        .join(" · ")}
                    </p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-app-faint">Not enough of your White games with these filters.</p>
          )}
        </div>
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-app-text">
            <Users className="h-4 w-4 text-app-faint" /> You with Black
          </h3>
          {m.you_black.length ? (
            <div className="grid gap-3">
              {m.you_black.map((row) => (
                <div key={row.their_move} className="rounded-lg border border-app-border bg-app-raised/50 px-3 py-2.5">
                  <p className="text-sm text-app-text">
                    vs <span className="font-mono font-semibold">1. {row.their_move}</span>{" "}
                    <span className="text-xs text-app-muted">({pct(row.their_share)} of their White games)</span>
                  </p>
                  {row.options.length ? (
                    <ul className="mt-1.5 grid gap-1">
                      {row.options.map((o, i) => (
                        <li key={o.reply} className="flex items-center justify-between text-xs">
                          <span className={i === 0 ? "font-semibold text-app-text" : "text-app-muted"}>
                            <span className="font-mono">1… {o.reply}</span> — you {pct(o.your_score_pct)} ({o.your_games}), they{" "}
                            {o.their_games ? `${pct(o.their_score_pct)} (${o.their_games})` : "untested"}
                          </span>
                          <Delta value={o.edge} decimals={0} />
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-xs text-app-faint">You haven't faced 1. {row.their_move} enough times.</p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-app-faint">They have no White first move with 3+ games.</p>
          )}
        </div>
      </div>
    </Card>
  );
}

// ── methodology ───────────────────────────────────────────────────────────────

function Methodology({ report }: { report: ScoutingReport }) {
  return (
    <details className="surface p-5 text-sm text-app-muted">
      <summary className="flex cursor-pointer items-center gap-2 font-medium text-app-text">
        <Cpu className="h-4 w-4 text-app-faint" /> How this is calculated
      </summary>
      <ul className="mt-3 grid list-disc gap-1.5 pl-5">
        <li>
          <b className="text-app-text">vs rating</b> is their actual score minus the Elo-expected score against the opponents they
          actually met. Rankings use a version shrunk toward zero so small samples can't top the lists.
        </li>
        <li>
          <b className="text-app-text">Book depth</b> counts how many of their own moves follow their most common choice before
          they deviate or reach a position they've seen fewer than three times.
        </li>
        <li>
          <b className="text-app-text">Clock</b> numbers come from the move timestamps Chess.com stores, as a share of the starting
          time so blitz and rapid compare fairly. A move that costs them 2.5× their normal time is flagged.
        </li>
        <li>
          <b className="text-app-text">Eval@12</b>{" "}
          {report.engine.enabled && report.engine.available
            ? `is Stockfish (depth ${report.engine.depth}) on the position after Black's 12th move, from their side, clipped at ±8.`
            : "needs the engine check turned on."}
        </li>
        <li>Dots: green = 12+ games, amber = 5–11, grey = fewer (treat as a hint).</li>
      </ul>
    </details>
  );
}
