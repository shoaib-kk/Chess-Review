import { Button } from "./ui/Button";

interface HeaderProps {
  apiStatus: "checking" | "ok" | "down";
  activeMode: "chesscom" | "pgn" | "insights";
  onModeChange: (mode: "chesscom" | "pgn" | "insights") => void;
  onNewReview?: () => void;
}

export function Header({ apiStatus, activeMode, onModeChange, onNewReview }: HeaderProps) {
  const statusClass =
    apiStatus === "ok"
      ? "bg-app-good"
      : apiStatus === "checking"
        ? "bg-app-warning"
        : "bg-app-blunder";

  return (
    <header className="border-b border-app-border/70 bg-app-bg/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-5 sm:flex-row sm:items-center sm:justify-between lg:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-app-lightSquare text-sm font-black text-slate-950 shadow-panel">
            CR
          </div>
          <div className="min-w-0">
            <h1 className="text-xl font-bold tracking-normal text-app-text">Chess Review</h1>
            <p className="truncate text-sm text-app-muted">Analyze your games with Stockfish</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="mr-1 hidden items-center gap-2 rounded-md bg-app-panel px-3 py-2 text-xs text-app-muted ring-1 ring-app-border/70 sm:flex">
            <span className={`h-2 w-2 rounded-full ${statusClass}`} />
            API {apiStatus}
          </div>
          {onNewReview && (
            <Button variant="ghost" size="md" onClick={onNewReview}>
              New Review
            </Button>
          )}
          <Button
            variant={activeMode === "chesscom" ? "primary" : "secondary"}
            size="md"
            onClick={() => onModeChange("chesscom")}
          >
            Import Chess.com Game
          </Button>
          <Button
            variant={activeMode === "pgn" ? "primary" : "secondary"}
            size="md"
            onClick={() => onModeChange("pgn")}
          >
            Paste PGN
          </Button>
          <Button
            variant={activeMode === "insights" ? "primary" : "secondary"}
            size="md"
            onClick={() => onModeChange("insights")}
          >
            Player Insights
          </Button>
        </div>
      </div>
    </header>
  );
}
