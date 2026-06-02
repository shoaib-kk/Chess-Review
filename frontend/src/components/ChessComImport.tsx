import { useMemo, useState } from "react";
import type { ChessComGame } from "../types";

interface ChessComImportProps {
  loading: boolean;
  onFetchGames: (username: string) => Promise<ChessComGame[]>;
  onAnalyzeGame: (username: string, pgn: string) => void;
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

export function ChessComImport({ loading, onFetchGames, onAnalyzeGame }: ChessComImportProps) {
  const [username, setUsername] = useState("");
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
    <section className="rounded bg-app-panel p-5 shadow-panel">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-50">Chess.com Import</h2>
        <p className="text-sm text-slate-400">Fetch recent public games and review one from your perspective.</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          className="min-h-11 flex-1 rounded border border-white/10 bg-slate-950 px-3 text-slate-100 outline-none focus:border-app-accent"
          value={username}
          placeholder="Chess.com username"
          onChange={(event) => setUsername(event.target.value)}
        />
        <button
          className="rounded bg-app-accent px-4 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:bg-slate-700"
          disabled={!username.trim() || fetching}
          onClick={fetchGames}
        >
          {fetching ? "Fetching..." : "Fetch Recent Games"}
        </button>
      </div>

      {games.length > 0 && (
        <div className="mt-4 grid gap-3">
          <select
            className="rounded border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-app-accent"
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
            <div className="rounded bg-slate-950 p-4">
              <div className="grid gap-3 text-sm sm:grid-cols-3">
                <Meta label="Opponent" value={selectedMeta.opponent} />
                <Meta label="Color" value={selectedMeta.color} />
                <Meta label="Result" value={selectedMeta.playerResult} />
                <Meta label="Time Class" value={selectedGame.time_class ?? "-"} />
                <Meta label="Date" value={selectedGame.date ?? "-"} />
                <Meta label="Rated" value={selectedGame.rated ? "Rated" : "Unrated"} />
              </div>
              <button
                className="mt-4 rounded bg-app-accent px-4 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:bg-slate-700"
                disabled={loading}
                onClick={() => onAnalyzeGame(username.trim(), selectedGame.pgn)}
              >
                {loading ? "Analysing..." : "Analyze Game"}
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 font-semibold text-slate-100">{value}</div>
    </div>
  );
}
