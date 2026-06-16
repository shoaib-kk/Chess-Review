import { BarChart3, BookOpen, Download, FileText, Home, LogOut, Puzzle, RotateCcw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Button } from "./ui/Button";

type Mode = "home" | "chesscom" | "pgn" | "insights" | "repertoire" | "puzzles";

interface HeaderProps {
  activeMode: Mode;
  onModeChange: (mode: Mode) => void;
  username: string;
  onLogout: () => void;
  onNewReview?: () => void;
}

const navItems: { mode: Mode; label: string; icon: LucideIcon; title: string }[] = [
  { mode: "home", label: "Home", icon: Home, title: "Start here — overview of everything you can do" },
  { mode: "chesscom", label: "Import Game", icon: Download, title: "Import and review your Chess.com games" },
  { mode: "pgn", label: "Paste a game (PGN)", icon: FileText, title: "Paste a PGN from any source to review it" },
  { mode: "insights", label: "Player Insights", icon: BarChart3, title: "Accuracy, mistakes and trends over time" },
  { mode: "repertoire", label: "Repertoire", icon: BookOpen, title: "Your openings and where to improve" },
  { mode: "puzzles", label: "Puzzles", icon: Puzzle, title: "Tactics built from your own games" },
];

export function Header({ activeMode, onModeChange, username, onLogout, onNewReview }: HeaderProps) {
  return (
    <aside className="border-app-border bg-app-panel/40 backdrop-blur-sm lg:fixed lg:inset-y-0 lg:left-0 lg:z-20 lg:w-60 lg:border-r">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-5 lg:h-full lg:px-4 lg:py-6">
        <div className="min-w-0">
          <h1 className="text-base font-semibold tracking-tight text-app-text">Chess Review</h1>
          <p className="truncate text-xs text-app-muted">Analysis workspace</p>
        </div>

        <button
          type="button"
          onClick={() => onModeChange("home")}
          title={username ? "Chess.com username — manage on Home" : "Set your Chess.com username on Home"}
          className="min-w-0 rounded-lg border border-app-border bg-app-panelSecondary/50 px-3 py-2.5 text-left transition hover:border-app-borderStrong hover:bg-app-panelSecondary"
        >
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-app-muted">Chess.com</p>
          <p className="mt-0.5 truncate font-mono text-sm font-medium text-app-text">
            {username || <span className="text-app-faint">Guest — set a username</span>}
          </p>
        </button>

        <nav className="flex flex-wrap gap-1.5 lg:grid lg:gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = activeMode === item.mode;
            return (
              <button
                key={item.mode}
                onClick={() => onModeChange(item.mode)}
                title={item.title}
                aria-current={active ? "page" : undefined}
                className={`group relative flex h-10 items-center gap-3 rounded-lg px-3 text-left text-sm font-medium transition lg:w-full ${
                  active
                    ? "bg-app-accentSoft text-app-text"
                    : "text-app-muted hover:bg-app-panelSecondary/70 hover:text-app-text"
                }`}
              >
                {active && <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-app-accent" />}
                <Icon
                  className={`h-[18px] w-[18px] shrink-0 transition ${active ? "text-app-accent" : "text-app-faint group-hover:text-app-muted"}`}
                  strokeWidth={2}
                />
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="flex flex-wrap items-center gap-2 lg:mt-auto lg:grid lg:gap-2">
          {onNewReview && (
            <Button variant="ghost" size="md" className="justify-start lg:w-full" onClick={onNewReview}>
              <RotateCcw className="h-4 w-4" />
              New Review
            </Button>
          )}
          <Button
            variant="ghost"
            size="md"
            className="justify-start lg:w-full"
            onClick={onLogout}
            title={username ? "Clear username and start over" : "Clear current session"}
          >
            <LogOut className="h-4 w-4" />
            {username ? "Change User" : "Reset"}
          </Button>
        </div>
      </div>
    </aside>
  );
}
