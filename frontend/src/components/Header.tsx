import { Button } from "./ui/Button";

interface HeaderProps {
  apiStatus: "checking" | "ok" | "down";
  activeMode: "chesscom" | "pgn" | "insights" | "repertoire";
  onModeChange: (mode: "chesscom" | "pgn" | "insights" | "repertoire") => void;
  username: string;
  onLogout: () => void;
  onNewReview?: () => void;
}

const navItems = [
  { mode: "chesscom", label: "Import Game" },
  { mode: "pgn", label: "Paste PGN" },
  { mode: "insights", label: "Player Insights" },
  { mode: "repertoire", label: "Opening Repertoire" },
] as const;

export function Header({ apiStatus, activeMode, onModeChange, username, onLogout, onNewReview }: HeaderProps) {
  return (
    <aside className="border-b-[0.5px] border-app-border bg-app-bg lg:fixed lg:inset-y-0 lg:left-0 lg:z-20 lg:w-72 lg:border-b-0 lg:border-r-[0.5px]">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 lg:h-full lg:px-5 lg:py-5">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center border-[0.5px] border-app-border text-sm font-medium text-app-text">
            CR
          </div>
          <div className="min-w-0">
            <h1 className="text-xl font-medium tracking-normal text-app-text">Chess Review</h1>
            <p className="truncate text-sm text-app-muted">Analyze your games with Stockfish</p>
          </div>
        </div>

        <div className="min-w-0 px-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-app-muted">Signed in as</p>
          <p className="mt-1 truncate font-mono text-sm font-medium text-app-text">{username}</p>
        </div>

        <div className="flex flex-wrap gap-2 lg:grid">
          {navItems.map((item) => (
            <Button
              key={item.mode}
              variant={activeMode === item.mode ? "primary" : "secondary"}
              size="md"
              className="justify-start lg:w-full"
              onClick={() => onModeChange(item.mode)}
            >
              {item.label}
            </Button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2 lg:mt-auto lg:grid">
          <div className="flex h-9 items-center px-1" title={`API ${apiStatus}`}>
            <span className="h-2.5 w-2.5 bg-app-text" />
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
