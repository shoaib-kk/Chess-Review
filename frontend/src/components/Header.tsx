import {
  BarChart3,
  BookOpen,
  Download,
  FileText,
  Home,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Puzzle,
  RotateCcw,
  Swords,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { ChessGlyph } from "./ui/ChessGlyph";

type Mode = "home" | "chesscom" | "pgn" | "insights" | "repertoire" | "puzzles" | "twin";

interface HeaderProps {
  activeMode: Mode;
  onModeChange: (mode: Mode) => void;
  username: string;
  onLogout: () => void;
  onNewReview?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

interface NavItem {
  mode: Mode;
  label: string;
  icon: LucideIcon;
  title: string;
}

const navSections: { heading: string; items: NavItem[] }[] = [
  {
    heading: "Workspace",
    items: [
      { mode: "home", label: "Dashboard", icon: Home, title: "Overview of your recent progress" },
      { mode: "chesscom", label: "Import Game", icon: Download, title: "Import and review your Chess.com games" },
      { mode: "pgn", label: "Paste PGN", icon: FileText, title: "Paste a PGN from any source to review it" },
    ],
  },
  {
    heading: "Analysis",
    items: [
      { mode: "insights", label: "Insights", icon: BarChart3, title: "Win rate, accuracy, and trends over time" },
      { mode: "repertoire", label: "Repertoire", icon: BookOpen, title: "Your openings and where to improve" },
      { mode: "puzzles", label: "Puzzles", icon: Puzzle, title: "Tactics built from your own games" },
    ],
  },
  {
    heading: "Digital Twin",
    items: [
      { mode: "twin", label: "Player Twin", icon: Swords, title: "Model your style and play against your digital twin" },
    ],
  },
];

export function Header({
  activeMode,
  onModeChange,
  username,
  onLogout,
  onNewReview,
  collapsed = false,
  onToggleCollapse,
}: HeaderProps) {
  return (
    <aside
      className={`glass border-b border-white/5 lg:fixed lg:inset-y-0 lg:left-0 lg:z-30 lg:border-b-0 lg:border-r lg:border-app-border lg:shadow-[1px_0_24px_-12px_rgba(0,0,0,0.8)] lg:transition-[width] lg:duration-300 lg:ease-spring ${
        collapsed ? "lg:w-[76px]" : "lg:w-64"
      }`}
    >
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-3 py-4 lg:h-full lg:py-5">
        {/* Brand */}
        <div className={`flex items-center gap-2.5 px-1 ${collapsed ? "lg:justify-center lg:px-0" : ""}`}>
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-app-accentLine bg-accent-sheen text-lg text-app-accent shadow-sheen">
            <ChessGlyph piece="knight" />
          </span>
          {!collapsed && (
            <div className="min-w-0">
              <h1 className="text-sm font-semibold tracking-tight text-app-text">Chess Review</h1>
              <p className="truncate text-[11px] text-app-subtle">Analysis workspace</p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav
          className={`-mx-1 flex gap-1 overflow-x-auto px-1 pb-1 lg:mx-0 lg:flex-col lg:gap-4 lg:overflow-visible lg:px-0 lg:pb-0 ${
            collapsed ? "lg:items-center" : ""
          }`}
        >
          {navSections.map((section) => (
            <div key={section.heading} className="contents lg:block">
              {!collapsed && (
                <p className="mb-1.5 hidden px-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-app-subtle lg:block">
                  {section.heading}
                </p>
              )}
              <div className={`flex gap-1 lg:flex-col ${collapsed ? "lg:items-center" : ""}`}>
                {section.items.map((item) => {
                  const Icon = item.icon;
                  const active = activeMode === item.mode;
                  return (
                    <button
                      key={item.mode}
                      onClick={() => onModeChange(item.mode)}
                      title={item.title}
                      aria-current={active ? "page" : undefined}
                      className={`group relative flex h-10 shrink-0 items-center gap-3 rounded-lg text-left text-sm font-medium transition duration-150 ease-spring lg:w-full ${
                        collapsed ? "lg:w-10 lg:justify-center lg:px-0" : "px-3"
                      } ${
                        active
                          ? "bg-app-accentSoft text-app-text shadow-sheen ring-1 ring-inset ring-app-accentLine"
                          : "text-app-muted hover:bg-white/[0.04] hover:text-app-text"
                      } px-3`}
                    >
                      {active && !collapsed && (
                        <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-app-accent" />
                      )}
                      <Icon
                        className={`h-[18px] w-[18px] shrink-0 transition group-hover:scale-105 ${
                          active ? "text-app-accent" : "text-app-faint group-hover:text-app-muted"
                        }`}
                        strokeWidth={2}
                      />
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer: identity + actions */}
        <div className={`flex flex-wrap items-center gap-2 lg:mt-auto lg:flex-col lg:items-stretch lg:gap-1.5`}>
          {!collapsed && (
            <button
              type="button"
              onClick={() => onModeChange("home")}
              title={username ? "Chess.com account" : "Set your Chess.com username on the dashboard"}
              className="hidden min-w-0 items-center gap-2.5 rounded-xl border border-app-border bg-app-raised/60 px-2.5 py-2 text-left transition hover:border-app-borderStrong hover:bg-app-raisedHover lg:flex"
            >
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-app-accentSoft text-[11px] font-bold uppercase text-app-accent">
                {username ? username.slice(0, 2) : "—"}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-mono text-[13px] font-medium text-app-text">
                  {username || "Guest"}
                </span>
                <span className="block text-[10px] text-app-subtle">{username ? "Chess.com" : "PGN review only"}</span>
              </span>
            </button>
          )}

          <div className={`flex gap-1.5 ${collapsed ? "lg:flex-col lg:items-center" : "lg:flex-col lg:items-stretch"}`}>
            {onNewReview && (
              <NavAction
                icon={RotateCcw}
                label="New Review"
                collapsed={collapsed}
                onClick={onNewReview}
                title="Start a new review"
              />
            )}
            <NavAction
              icon={LogOut}
              label={username ? "Change User" : "Reset"}
              collapsed={collapsed}
              onClick={onLogout}
              title={username ? "Clear username and start over" : "Clear current session"}
            />
          </div>

          {onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className={`hidden h-9 items-center gap-2 rounded-lg px-3 text-xs font-medium text-app-subtle transition hover:bg-white/[0.04] hover:text-app-text lg:flex ${
                collapsed ? "lg:w-10 lg:justify-center lg:px-0" : ""
              }`}
            >
              {collapsed ? <PanelLeftOpen className="h-[18px] w-[18px]" /> : <PanelLeftClose className="h-[18px] w-[18px]" />}
              {!collapsed && <span>Collapse</span>}
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}

function NavAction({
  icon: Icon,
  label,
  collapsed,
  onClick,
  title,
}: {
  icon: LucideIcon;
  label: string;
  collapsed: boolean;
  onClick: () => void;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`flex h-9 items-center gap-2 rounded-lg text-sm font-medium text-app-muted transition hover:bg-white/[0.04] hover:text-app-text ${
        collapsed ? "lg:w-10 lg:justify-center lg:px-0" : "px-3 lg:w-full"
      }`}
    >
      <Icon className="h-4 w-4 shrink-0" strokeWidth={2} />
      {!collapsed && <span className="truncate">{label}</span>}
    </button>
  );
}
