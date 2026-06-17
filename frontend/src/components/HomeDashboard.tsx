import { useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Download,
  FileText,
  Play,
  Puzzle,
  Sparkles,
  Swords,
} from "lucide-react";
import { ApiStatusIndicator } from "./ApiStatusIndicator";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";
import { SAMPLE_GAME_LABEL } from "../data/sampleGame";

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
}

interface ToolCard {
  icon: LucideIcon;
  title: string;
  description: string;
  action: string;
  onClick: () => void;
  needsUsername: boolean;
}

export function HomeDashboard({
  apiStatus,
  username,
  onUsernameChange,
  onImportGame,
  onPastePgn,
  onTrySample,
  onOpenInsights,
  onOpenRepertoire,
  onOpenPuzzles,
  sampleLoading,
}: HomeDashboardProps) {
  const [draftUsername, setDraftUsername] = useState(username);
  const hasUsername = Boolean(username.trim());

  function saveUsername(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onUsernameChange(draftUsername.trim());
  }

  const tools: ToolCard[] = [
    {
      icon: Download,
      title: "Import a game",
      description: "Pull your recent games straight from Chess.com and review any one of them.",
      action: "Review one of your games",
      onClick: onImportGame,
      needsUsername: true,
    },
    {
      icon: FileText,
      title: "Paste a game (PGN)",
      description: "Have a game from anywhere? Paste its PGN and get a full move-by-move review.",
      action: "Paste a PGN",
      onClick: onPastePgn,
      needsUsername: false,
    },
    {
      icon: BarChart3,
      title: "Player insights",
      description: "See your accuracy, recurring mistakes, and how your play trends over time.",
      action: "See your insights",
      onClick: onOpenInsights,
      needsUsername: true,
    },
    {
      icon: BookOpen,
      title: "Opening repertoire",
      description: "Discover which openings you play, your win rates, and where to improve.",
      action: "Explore your openings",
      onClick: onOpenRepertoire,
      needsUsername: true,
    },
    {
      icon: Puzzle,
      title: "Puzzles",
      description: "Train on tactics taken from the mistakes in your own real games.",
      action: "Train with puzzles",
      onClick: onOpenPuzzles,
      needsUsername: true,
    },
  ];

  return (
    <div className="mx-auto w-full max-w-5xl animate-fade-in">
      {/* Hero */}
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-6 px-6 py-7 sm:px-8 sm:py-8">
          <div className="flex items-start gap-4">
            <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-app-accent to-[#8b5cf6] text-white shadow-glow">
              <Swords className="h-6 w-6" strokeWidth={2.25} />
            </div>
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold tracking-tight text-app-text">Welcome to Chess Review</h1>
              <p className="mt-1 text-sm text-app-muted">
                Analyze your chess like a coach would. Start with a sample game, paste any PGN, or connect your
                Chess.com username for personal insights.
              </p>
            </div>
          </div>

          {/* Primary actions */}
          <div className="grid gap-3 sm:grid-cols-2">
            <button
              onClick={onTrySample}
              disabled={sampleLoading}
              className="group flex items-center gap-4 rounded-xl border border-app-accent/40 bg-app-accentSoft px-4 py-4 text-left transition hover:border-app-accent/70 disabled:cursor-not-allowed disabled:opacity-70"
            >
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-app-accent text-white shadow-sm">
                {sampleLoading ? (
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                ) : (
                  <Play className="h-5 w-5" strokeWidth={2.25} />
                )}
              </span>
              <span className="min-w-0">
                <span className="flex items-center gap-1.5 text-sm font-semibold text-app-text">
                  Try a sample game
                  <Sparkles className="h-3.5 w-3.5 text-app-accent" />
                </span>
                <span className="mt-0.5 block truncate text-xs text-app-muted">
                  {sampleLoading ? "Analyzing the sample game..." : "No account needed - see a full review instantly"}
                </span>
              </span>
            </button>

            <button
              onClick={onImportGame}
              className="group flex items-center gap-4 rounded-xl border border-app-border bg-app-panelSecondary/60 px-4 py-4 text-left transition hover:border-app-borderStrong hover:bg-app-panelHover"
            >
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-app-panel text-app-accent ring-1 ring-app-border">
                <Download className="h-5 w-5" strokeWidth={2.25} />
              </span>
              <span className="min-w-0">
                <span className="text-sm font-semibold text-app-text">Review one of your games</span>
                <span className="mt-0.5 block truncate text-xs text-app-muted">
                  Import public games from Chess.com
                </span>
              </span>
            </button>
          </div>

          {/* Username connect */}
          <div className="rounded-xl border border-app-border bg-app-panelSecondary/40 px-4 py-4">
            <form className="flex flex-col gap-3 sm:flex-row sm:items-end" onSubmit={saveUsername}>
              <label className="grid flex-1 gap-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-app-muted">
                  Enter your Chess.com username
                </span>
                <input
                  className="h-11 rounded-lg border border-app-border bg-app-panel px-3 text-app-text outline-none transition placeholder:text-app-faint focus-visible:ring-2 focus-visible:ring-app-accent/50 focus:border-app-borderStrong"
                  value={draftUsername}
                  placeholder="e.g. hikaru"
                  onChange={(event) => setDraftUsername(event.target.value)}
                />
              </label>
              <Button variant="primary" type="submit" disabled={!draftUsername.trim() || draftUsername.trim() === username.trim()}>
                {hasUsername ? "Update" : "Save username"}
                <ArrowRight className="h-4 w-4" />
              </Button>
            </form>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-app-faint">
                We only read your public Chess.com games. No password needed.
              </p>
              <ApiStatusIndicator status={apiStatus} />
            </div>
          </div>
        </div>
      </Card>

      {/* Tool guide */}
      <div className="mt-6">
        <h2 className="px-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-app-muted">What you can do</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {tools.map((tool) => {
            const Icon = tool.icon;
            const locked = tool.needsUsername && !hasUsername;
            return (
              <button
                key={tool.title}
                onClick={tool.onClick}
                className="group flex h-full flex-col items-start gap-3 rounded-xl border border-app-border bg-app-panel p-4 text-left shadow-card transition hover:border-app-borderStrong hover:bg-app-panelHover"
              >
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-app-accentSoft text-app-accent">
                  <Icon className="h-[18px] w-[18px]" strokeWidth={2} />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-app-text">{tool.title}</span>
                  <span className="mt-1 block text-xs leading-relaxed text-app-muted">{tool.description}</span>
                </span>
                <span className="mt-auto flex items-center gap-1.5 pt-1 text-xs font-medium text-app-accent">
                  {tool.action}
                  <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
                  {locked && (
                    <span className="ml-1 rounded-full bg-app-panelSecondary px-2 py-0.5 text-[10px] font-medium text-app-faint">
                      uses Chess.com username
                    </span>
                  )}
                </span>
              </button>
            );
          })}

          {/* Sample game tile to round out the grid */}
          <button
            onClick={onTrySample}
            disabled={sampleLoading}
            className="group flex h-full flex-col items-start gap-3 rounded-xl border border-app-accent/30 bg-app-accentSoft p-4 text-left shadow-card transition hover:border-app-accent/60 disabled:cursor-not-allowed disabled:opacity-70"
          >
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-app-accent text-white">
              <Play className="h-[18px] w-[18px]" strokeWidth={2.25} />
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-app-text">Not sure where to start?</span>
              <span className="mt-1 block text-xs leading-relaxed text-app-muted">
                Watch a full review of {SAMPLE_GAME_LABEL}. No account required.
              </span>
            </span>
            <span className="mt-auto flex items-center gap-1.5 pt-1 text-xs font-medium text-app-accent">
              {sampleLoading ? "Analyzing..." : "Try a sample game"}
              <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
