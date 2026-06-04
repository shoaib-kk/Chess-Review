import { Button } from "./ui/Button";
import { ApiStatusIndicator } from "./ApiStatusIndicator";

interface HeaderProps {
  apiStatus: "checking" | "ok" | "down";
  activeMode: "chesscom" | "pgn" | "insights" | "repertoire";
  onModeChange: (mode: "chesscom" | "pgn" | "insights" | "repertoire") => void;
  username: string;
  onLogout: () => void;
  onNewReview?: () => void;
}

const navItems = [
  { mode: "chesscom", label: "Import Game", icon: "+" },
  { mode: "pgn", label: "Paste PGN", icon: "P" },
  { mode: "insights", label: "Player Insights", icon: "I" },
  { mode: "repertoire", label: "Repertoire", icon: "R" },
] as const;

export function Header({ apiStatus, activeMode, onModeChange, username, onLogout, onNewReview }: HeaderProps) {
  return (
    <aside className="bg-app-bg lg:fixed lg:inset-y-0 lg:left-0 lg:z-20 lg:w-60">
      <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-5 lg:h-full lg:px-4 lg:py-5">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-8 w-8 shrink-0 place-items-center bg-app-panelSecondary text-xs font-medium text-app-text">
            CR
          </div>
          <div className="min-w-0">
            <h1 className="text-base font-medium tracking-normal text-app-text">Chess Review</h1>
            <p className="truncate text-xs text-app-muted">Analysis workspace</p>
          </div>
        </div>

        <div className="min-w-0 px-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-app-muted">Signed in as</p>
          <p className="mt-1 truncate font-mono text-sm font-medium text-app-text">{username}</p>
        </div>

        <div className="flex flex-wrap gap-1 lg:grid">
          {navItems.map((item) => (
            <button
              key={item.mode}
              className={`grid h-9 grid-cols-[22px_1fr] items-center gap-2 px-2 text-left text-sm font-medium transition hover:bg-app-panelSecondary lg:w-full ${
                activeMode === item.mode ? "bg-app-panelSecondary text-app-text" : "text-app-muted"
              }`}
              onClick={() => onModeChange(item.mode)}
            >
              <span className="grid h-5 w-5 place-items-center font-mono text-xs">{item.icon}</span>
              <span className="truncate">{item.label}</span>
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2 lg:mt-auto lg:grid">
          <div className="flex h-9 items-center px-1">
            <ApiStatusIndicator status={apiStatus} />
          </div>
          {onNewReview && (
            <Button variant="ghost" size="md" className="justify-start lg:w-full" onClick={onNewReview}>
              New Review
            </Button>
          )}
          <Button variant="ghost" size="md" className="justify-start lg:w-full" onClick={onLogout}>
            Change User
          </Button>
        </div>
      </div>
    </aside>
  );
}
