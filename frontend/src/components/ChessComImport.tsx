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
    <Card className="overflow-hidden">
      <CardHeader title="Import from Chess.com" eyebrow="Game history">
        Fetch recent public games and review one from your perspective.
      </CardHeader>

      <div className="px-5 pb-5">
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          className="h-11 flex-1 border-[0.5px] border-app-border bg-app-panel px-3 text-app-text outline-none transition placeholder:text-[#9b9b9b] focus:border-app-text"
          value={username}
          placeholder="Chess.com username"
          onChange={(event) => onUsernameChange(event.target.value)}
        />
        <Button variant="primary" disabled={!username.trim() || fetching} onClick={fetchGames}>
          {fetching ? "Fetching..." : "Fetch Recent Games"}
        </Button>
      </div>

      {games.length > 0 && (
        <div className="mt-4 grid gap-3">
          <select
            className="h-11 border-[0.5px] border-app-border bg-app-panel px-3 text-sm text-app-text outline-none transition focus:border-app-text"
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
            <div className="border-[0.5px] border-app-border bg-app-panel p-4">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-app-text">{selectedMeta.color} vs {selectedMeta.opponent}</div>
                  <div className="mt-1 text-xs text-app-muted">{selectedGame.date ?? "Unknown date"}</div>
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
                <div className="flex flex-wrap items-center gap-2 border-b-[0.5px] border-app-border">
                  {(["fast", "normal", "deep"] as AnalysisMode[]).map((item) => (
                    <button
                      key={item}
                      className={`h-8 border-b-[1px] px-3 text-xs font-medium capitalize transition ${
                        mode === item ? "border-app-text text-app-text" : "border-transparent text-app-muted hover:bg-app-panelSecondary hover:text-app-text"
                      }`}
                      onClick={() => onModeChange(item)}
                    >
                      {item}
                    </button>
                  ))}
                </div>
                <Button className="w-full sm:w-auto" variant="primary" disabled={loading} onClick={() => onAnalyzeGame(username.trim(), selectedGame.pgn, mode)}>
                  {loading ? "Analysing..." : "Analyze Game"}
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
      <div className="text-xs uppercase tracking-wide text-app-muted">{label}</div>
      <div className="mt-1 font-medium text-app-text">{value}</div>
    </div>
  );
}
