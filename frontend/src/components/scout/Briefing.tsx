import { ArrowRight, BookOpen, Brain, Cpu, Eye, Lightbulb, ShieldX, Sparkles, Target, X } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import type { ScoutDeepResult, ScoutingReport } from "../../types";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Delta } from "../ui/Delta";
import { GLOSSARY, InfoTip } from "./InfoTip";
import { pct } from "./shared";
import type { OpenLine, Side } from "./shared";

export type ScoutTab = "briefing" | "openings" | "habits" | "deep";

type StepKind = "play" | "avoid" | "punish" | "expect" | "watch";

interface Step {
  kind: StepKind;
  title: string;
  detail: string;
  line?: { side: Side; path: string[] };
}

const KIND_META: Record<StepKind, { label: string; icon: typeof Target; tone: string }> = {
  play: { label: "Play this", icon: Target, tone: "bg-app-good/10 text-app-good ring-app-good/30" },
  punish: { label: "Punish", icon: Sparkles, tone: "bg-app-brilliant/10 text-app-brilliant ring-app-brilliant/30" },
  avoid: { label: "Avoid", icon: ShieldX, tone: "bg-app-blunder/10 text-app-blunder ring-app-blunder/30" },
  expect: { label: "Expect", icon: BookOpen, tone: "bg-app-panelSecondary text-app-muted ring-app-border" },
  watch: { label: "Watch for", icon: Eye, tone: "bg-app-warning/10 text-app-warning ring-app-warning/30" },
};

const COACH_KEY = "cr_scout_coach_dismissed";

function readFlag(key: string): boolean {
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

/** Build the numbered plan for the chosen colour from every source we have. */
export function buildSteps(report: ScoutingReport, you: Side, deep: ScoutDeepResult | null): Step[] {
  const opp: Side = you === "white" ? "black" : "white";
  const steps: Step[] = [];

  // Backend's plain-language plan (skip its "Steer into" lines; we render those with board links below).
  const planLines = (you === "white" ? report.game_plan.you_white : report.game_plan.you_black).filter(
    (text) => !text.startsWith("Steer into"),
  );
  for (const text of planLines.slice(0, 3)) {
    const kind: StepKind = /^(Avoid|Be careful)/.test(text)
      ? "avoid"
      : /^(Open|Answer with|Their weakest)/.test(text)
        ? "play"
        : "expect";
    const [title, ...rest] = text.split(/:\s|—\s/);
    const detail = rest.join(" — ").trim();
    steps.push({ kind, title: title.trim(), detail: detail.charAt(0).toUpperCase() + detail.slice(1) });
  }

  for (const entry of report.steer_into.filter((e) => e.opponent_color === opp).slice(0, 2)) {
    steps.push({
      kind: "play",
      title: `Aim for ${entry.line}`,
      detail: `They score ${pct(entry.score_pct)} from here${
        entry.expected_pct !== null ? `, when their rating says ${pct(entry.expected_pct)}` : ""
      } (${entry.games} games).`,
      line: { side: opp, path: entry.path },
    });
  }

  for (const ref of (deep?.refutations ?? []).filter((r) => r.opponent_color === opp).slice(0, 2)) {
    steps.push({
      kind: "punish",
      title: `After ${ref.line}, they play ${ref.their_move}: punish it with ${ref.punish_move}`,
      detail: `They chose ${ref.their_move} in ${pct(ref.their_share)} of their games here, but Stockfish rates it a ${ref.severity} (${(
        ref.loss_cp / 100
      ).toFixed(1)} pawns). Their better move was ${ref.best_move}.`,
      line: { side: opp, path: [...ref.path, ref.their_move] },
    });
  }

  for (const trap of (deep?.lichess_traps ?? []).filter((t) => t.opponent_color === opp).slice(0, 1)) {
    steps.push({
      kind: "punish",
      title: `Set the trap after ${trap.line}`,
      detail: `${pct(trap.trap_share)} of players at their rating answer ${trap.trap_move} here and score only ${pct(trap.trap_score_pct)}.`,
      line: { side: opp, path: trap.path },
    });
  }

  const avoid = report.avoid.find((e) => e.opponent_color === opp);
  if (avoid) {
    steps.push({
      kind: "avoid",
      title: `Steer clear of ${avoid.line}`,
      detail: `Their home turf: they score ${pct(avoid.score_pct)}${
        avoid.expected_pct !== null ? ` against an expected ${pct(avoid.expected_pct)}` : ""
      } (${avoid.games} games).`,
      line: { side: opp, path: avoid.path },
    });
  }

  // Don't suggest a line we just told them to avoid (a strong-but-inconsistent spot reads as a contradiction).
  const avoided = new Set<string>(report.avoid.filter((e) => e.opponent_color === opp).map((e) => e.path.join(" ")));
  for (const text of planLines) {
    const careful = /^Be careful with 1\.\.\.(\S+)/.exec(text);
    const firstMove = report.as_white.first_moves[0]?.move;
    if (careful && firstMove) avoided.add(`${firstMove} ${careful[1]}`);
  }
  const unsure = report.decision_points.find(
    (d) => d.opponent_color === opp && ![...avoided].some((p) => d.path.join(" ").startsWith(p)),
  );
  if (unsure) {
    steps.push({
      kind: "watch",
      title: `They get unsure after ${unsure.line}`,
      detail: `${unsure.reason.charAt(0).toUpperCase()}${unsure.reason.slice(1)}. A good place to be.`,
      line: { side: opp, path: unsure.path },
    });
  }
  return steps.slice(0, 7);
}

export function Briefing({
  report,
  you,
  deep,
  deepRunning,
  onOpen,
  onTab,
  methodology,
}: {
  report: ScoutingReport;
  you: Side;
  deep: ScoutDeepResult | null;
  deepRunning: boolean;
  onOpen: OpenLine;
  onTab: (tab: ScoutTab) => void;
  methodology: ReactNode;
}) {
  const [coachHidden, setCoachHidden] = useState(() => readFlag(COACH_KEY));
  const opp: Side = you === "white" ? "black" : "white";
  const steps = buildSteps(report, you, deep);
  const theirSide = report.profile[opp];
  const losses = report.profile.terminations.loss.reduce((sum, row) => sum + row.games, 0);
  const timeLosses = report.profile.terminations.loss.find((row) => row.reason === "time")?.games ?? 0;
  const habits = report.game_plan.general.slice(0, 4);

  function dismissCoach() {
    setCoachHidden(true);
    try {
      localStorage.setItem(COACH_KEY, "1");
    } catch {
      /* fine */
    }
  }

  return (
    <div className="grid gap-5">
      {!coachHidden && (
        <div className="relative rounded-2xl border border-app-accentLine bg-accent-sheen p-4 pr-10 sm:p-5 sm:pr-12">
          <button
            type="button"
            onClick={dismissCoach}
            aria-label="Hide these tips"
            className="absolute right-3 top-3 rounded-md p-1 text-app-faint hover:bg-white/5 hover:text-app-text"
          >
            <X className="h-4 w-4" />
          </button>
          <p className="flex items-center gap-2 text-sm font-semibold text-app-text">
            <Lightbulb className="h-4 w-4 text-app-accent" /> How to use this
          </p>
          <ol className="mt-2 grid gap-1.5 text-sm text-app-muted sm:grid-cols-3 sm:gap-4">
            <li>
              <b className="text-app-text">1. Read the plan below.</b> It's ordered by what matters most for the colour you picked.
            </li>
            <li>
              <b className="text-app-text">2. Press "Show on board"</b> to see a line in their own games and click through it.
            </li>
            <li>
              <b className="text-app-text">3. Want more?</b> The tabs above go deeper. Every <span className="text-app-accent">?</span> explains a number.
            </li>
          </ol>
        </div>
      )}

      <Card>
        <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-accent/80">Your game plan</p>
            <h2 className="text-lg font-semibold tracking-tight text-app-text">
              Playing {you === "white" ? "White" : "Black"} against {report.username}
            </h2>
          </div>
          {!deep && (
            <button
              type="button"
              onClick={() => onTab("deep")}
              className="inline-flex items-center gap-1.5 text-xs text-app-muted hover:text-app-accent"
            >
              <Cpu className="h-3.5 w-3.5" />
              {deepRunning ? "Engine deep dive running: more tips soon" : "Add engine-checked tips"}
              <ArrowRight className="h-3 w-3" />
            </button>
          )}
        </div>

        {steps.length ? (
          <ol className="grid gap-3">
            {steps.map((step, i) => {
              const meta = KIND_META[step.kind];
              const Icon = meta.icon;
              return (
                <li key={`${step.kind}-${step.title}`} className="flex gap-3 rounded-xl border border-app-border bg-app-raised/50 p-3 sm:p-4">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-app-panelSecondary font-mono text-xs font-semibold text-app-text">
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <span className={`mb-1.5 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${meta.tone}`}>
                      <Icon className="h-3 w-3" /> {meta.label}
                    </span>
                    <p className="break-words text-sm font-semibold leading-snug text-app-text">{step.title}</p>
                    {step.detail && <p className="mt-0.5 text-sm leading-relaxed text-app-muted">{step.detail}</p>}
                  </div>
                  {step.line && (
                    <Button
                      variant="secondary"
                      size="sm"
                      className="shrink-0 self-center"
                      onClick={() => onOpen(step.line!.side, step.line!.path)}
                      aria-label={`Show ${step.title} on the board`}
                    >
                      <BookOpen className="h-4 w-4" />
                      <span className="hidden sm:inline">Show on board</span>
                    </Button>
                  )}
                </li>
              );
            })}
          </ol>
        ) : (
          <p className="text-sm text-app-faint">
            Not enough of their games as {opp === "white" ? "White" : "Black"} to make a plan yet. Try reading more games or all
            time controls.
          </p>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <div className="mb-3 flex items-center justify-between gap-2">
            <p className="flex items-center gap-2 text-sm font-semibold text-app-text">
              <Brain className="h-4 w-4 text-app-accent" /> Their habits
            </p>
            <button type="button" onClick={() => onTab("habits")} className="inline-flex items-center gap-1 text-xs text-app-muted hover:text-app-accent">
              See all <ArrowRight className="h-3 w-3" />
            </button>
          </div>
          {habits.length ? (
            <ul className="grid gap-2">
              {habits.map((text) => (
                <li key={text} className="rounded-lg bg-app-panelSecondary px-3 py-2 text-sm leading-relaxed text-app-muted">
                  {text}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-app-faint">No standout habits in this sample.</p>
          )}
        </Card>

        <Card>
          <p className="mb-3 text-sm font-semibold text-app-text">At a glance</p>
          <dl className="grid gap-3 text-sm">
            <Glance
              label={`Their score as ${opp === "white" ? "White" : "Black"}`}
              tip={<InfoTip label="Score">{GLOSSARY.score}</InfoTip>}
              value={pct(theirSide.score_pct)}
              note={theirSide.expected_pct !== null ? `expected ${pct(theirSide.expected_pct)}` : undefined}
            />
            <Glance
              label="Compared with their rating"
              tip={<InfoTip label="Compared with their rating">{GLOSSARY.vsExpected}</InfoTip>}
              value={<Delta value={theirSide.perf_delta} invert decimals={0} />}
              note={
                theirSide.perf_delta === null
                  ? undefined
                  : theirSide.perf_delta <= -3
                    ? "underperforms"
                    : theirSide.perf_delta >= 3
                      ? "overperforms"
                      : "about as expected"
              }
            />
            <Glance
              label="Losses on time"
              value={losses ? pct((timeLosses / losses) * 100) : "–"}
              note={`${timeLosses} of ${losses} losses`}
            />
          </dl>
        </Card>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <NextCard icon={BookOpen} title="Explore their openings" text="Click through their games move by move." onClick={() => onTab("openings")} />
        <NextCard icon={Brain} title="Habits & tilt" text="When they play worst, and what positions they hate." onClick={() => onTab("habits")} />
        <NextCard icon={Cpu} title="Engine deep dive" text="Their habitual mistakes and how they blunder." onClick={() => onTab("deep")} />
      </div>

      {methodology}
    </div>
  );
}

function Glance({ label, value, note, tip }: { label: string; value: ReactNode; note?: string; tip?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="flex items-center gap-1.5 text-app-muted">
        {label} {tip}
      </dt>
      <dd className="text-right">
        <span className="nums font-semibold text-app-text">{value}</span>
        {note && <span className="block text-[11px] text-app-faint">{note}</span>}
      </dd>
    </div>
  );
}

function NextCard({ icon: Icon, title, text, onClick }: { icon: typeof Target; title: string; text: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group rounded-2xl border border-app-border bg-app-raised/50 p-4 text-left transition hover:border-app-borderStrong hover:bg-app-raised"
    >
      <Icon className="h-5 w-5 text-app-accent" />
      <p className="mt-2 flex items-center gap-1 text-sm font-semibold text-app-text">
        {title} <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
      </p>
      <p className="mt-0.5 text-xs text-app-muted">{text}</p>
    </button>
  );
}
