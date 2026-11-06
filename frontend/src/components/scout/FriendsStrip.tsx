import { Users } from "lucide-react";
import { useEffect, useState } from "react";
import { fetchScoutWatchlist } from "../../api/client";
import type { ScoutWatchFriend } from "../../types";
import { Badge } from "../ui/Badge";
import { Surface } from "../ui/Surface";

/** Compact dashboard card: watched friends with new games and alerts. Hidden when empty or on error. */
export function FriendsStrip({ onScoutFriend }: { onScoutFriend: (username: string) => void }) {
  const [friends, setFriends] = useState<ScoutWatchFriend[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetchScoutWatchlist()
      .then((list) => {
        if (!cancelled) setFriends(list.friends);
      })
      .catch(() => {
        /* hide the card on failure */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!friends.length) return null;

  // Friends with news first.
  const sorted = [...friends].sort((a, b) => b.new_games + b.alerts.length - (a.new_games + a.alerts.length));

  return (
    <Surface variant="raised" className="p-5">
      <div className="mb-3 flex items-center gap-2">
        <Users className="h-4 w-4 text-app-accent" />
        <h2 className="text-sm font-semibold text-app-text">Friends</h2>
        <span className="text-xs text-app-faint">click to scout</span>
      </div>
      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {sorted.slice(0, 6).map((f) => (
          <li key={f.username}>
            <button
              type="button"
              onClick={() => onScoutFriend(f.username)}
              aria-label={`Scout ${f.username}${f.new_games ? `, ${f.new_games} new games` : ""}`}
              className="w-full rounded-lg border border-app-border bg-app-raised/50 px-3 py-2.5 text-left transition hover:border-app-borderStrong hover:bg-app-raised"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate font-mono text-sm font-semibold text-app-text">{f.username}</span>
                {f.new_games > 0 && <Badge tone="yellow">{`${f.new_games} new`}</Badge>}
              </div>
              <p className="mt-1 truncate text-xs text-app-muted">
                {f.alerts[0]?.message ?? Object.entries(f.ratings).map(([tc, r]) => `${tc} ${r}`).join(" · ")}
              </p>
            </button>
          </li>
        ))}
      </ul>
    </Surface>
  );
}
