import { Download, Search, Swords } from "lucide-react";
import { useMemo, useState } from "react";
import type { AnalysisMode, ChessComGame } from "../types";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";

interface ChessComImportProps {
  loading: boolean;
  username: string;
  onUsernameChange: (username: string) => void;
  mode: AnalysisMode;
  onModeChange: (mode: AnalysisMode) => void;
  onFetchGames: (username: string) => Promise<ChessComGame[]>;
  onAnalyzeGame: (username: string, pgn: string, mode: AnalysisMode) => void;
}

function sameUser(a: string, b: string) {
  return a.trim().toLowerCase() === b.trim().toLowerCase();
}

function gameMeta(game: ChessComGame, username: string) {
  const userIsWhite = sameUser(game.white_username, username);
  const opponent = userIsWhite ? game.black_username : game.white_username;
  const color = userIsWhite ? "White" : "Black";
  const playerResult = userIsWhite ? game.white_result : game.black_result;
  return { opponent, color, playerResult: playerResult ?? game.result };
}

export function ChessComImport({
  loading,
  username,
  onUsernameChange,
  mode,
  onModeChange,
  onFetchGames,
  onAnalyzeGame,
}: ChessComImportProps) {
  const [games, setGames] = useState<ChessComGame[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [fetching, setFetching] = useState(false);
  const selectedGame = games[selectedIndex];
  const modeLabels: Record<AnalysisMode, { label: string; help: string }> = {
    fast: { label: "Quick look", help: "Fastest review" },
    normal: { label: "Standard", help: "Balanced review" },
    deep: { label: "Thorough", help: "Slower, more careful review" },
  };

  const selectedMeta = useMemo(
    () => (selectedGame ? gameMeta(selectedGame, username) : null),
    [selectedGame, username],
  );

  async function fetchGames() {
    if (!username.trim()) return;
    setFetching(true);
    try {
      const result = await onFetchGames(username.trim());
      setGames(result);
      setSelectedIndex(0);
    } finally {
      setFetching(false);
    }
  }

  return (
    <Card>
      <CardHeader title="Import from Chess.com" eyebrow="Game history">
        Enter your Chess.com username to read your public games. No password needed.
      </CardHeader>

      <div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-app-faint" strokeWidth={2} />
          <input
            className="h-11 w-full rounded-lg border border-app-border bg-app-panelSecondary pl-9 pr-3 text-app-text outline-none transition placeholder:text-app-faint focus-visible:ring-2 focus-visible:ring-app-accent/50 focus:border-app-borderStrong"
            value={username}
            placeholder="Enter your Chess.com username"
            onChange={(event) => onUsernameChange(event.target.value)}
          />
        </div>
        <Button variant="primary" disabled={!username.trim() || fetching} onClick={fetchGames}>
          <Download className="h-4 w-4" />
          {fetching ? "Fetching..." : "Fetch public games"}
        </Button>
      </div>

      {games.length > 0 && (
        <div className="mt-4 grid gap-3">
          <select
            className="h-11 rounded-lg border border-app-border bg-app-panelSecondary px-3 text-sm text-app-text outline-none transition focus-visible:ring-2 focus-visible:ring-app-accent/50 focus:border-app-borderStrong"
            value={selectedIndex}
            onChange={(event) => setSelectedIndex(Number(event.target.value))}
          >
            {games.map((game, index) => {
              const meta = gameMeta(game, username);
              return (
                <option key={`${game.url ?? index}-${game.end_time ?? index}`} value={index}>
                  {game.date ?? "Unknown date"} - {meta.color} vs {meta.opponent} - {meta.playerResult}
                </option>
              );
            })}
          </select>

          {selectedGame && selectedMeta && (
            <div className="border-t border-app-border pt-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-app-panelSecondary text-app-muted">
                    <Swords className="h-[18px] w-[18px]" strokeWidth={2} />
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-app-text">{selectedMeta.color} vs {selectedMeta.opponent}</div>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-app-muted">
                      <span>{selectedGame.date ?? "Unknown date"}</span>
                      {selectedGame.time_class && <Badge tone="neutral">{selectedGame.time_class}</Badge>}
                    </div>
                  </div>
                </div>
                <Badge tone={selectedMeta.playerResult === "win" ? "green" : selectedMeta.playerResult === "resigned" || selectedMeta.playerResult === "checkmated" ? "red" : "neutral"}>
                  {selectedMeta.playerResult}
                </Badge>
              </div>
              <div className="grid gap-3 text-sm sm:grid-cols-3">
                <Meta label="Opponent" value={selectedMeta.opponent} />
                <Meta label="Color" value={selectedMeta.color} />
                <Meta label="Result" value={selectedMeta.playerResult} />
                <Meta label="Time Class" value={selectedGame.time_class ?? "-"} />
                <Meta label="Date" value={selectedGame.date ?? "-"} />
                <Meta label="Rated" value={selectedGame.rated ? "Rated" : "Unrated"} />
              </div>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="inline-flex items-center gap-1 rounded-lg border border-app-border bg-app-panelSecondary p-1">
                  {(["fast", "normal", "deep"] as AnalysisMode[]).map((item) => (
                    <button
                      key={item}
                      className={`h-8 rounded-md px-3 text-xs font-medium capitalize transition ${
                        mode === item ? "bg-app-accentSoft text-app-text" : "text-app-muted hover:bg-app-panelSecondary hover:text-app-text"
                      }`}
                      title={modeLabels[item].help}
                      onClick={() => onModeChange(item)}
                    >
                      {modeLabels[item].label}
                    </button>
                  ))}
                </div>
                <Button className="w-full sm:w-auto" variant="primary" disabled={loading} onClick={() => onAnalyzeGame(username.trim(), selectedGame.pgn, mode)}>
                  {loading ? "Analyzing..." : "Analyze Game"}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
      </div>
    </Card>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-app-faint">{label}</div>
      <div className="mt-1 truncate font-medium text-app-text">{value}</div>
    </div>
  );
}
