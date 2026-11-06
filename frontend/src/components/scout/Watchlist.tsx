import { AlertTriangle, Check, Crosshair, Eye, EyeOff, Trash2, Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  addScoutWatch,
  apiErrorMessage,
  fetchScoutWatchlist,
  markScoutWatchSeen,
  removeScoutWatch,
} from "../../api/client";
import type { ScoutWatchFriend } from "../../types";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardHeader } from "../ui/Card";

export interface WatchlistApi {
  friends: ScoutWatchFriend[];
  loading: boolean;
  error: string | null;
  busy: string | null;
  isWatching: (username: string) => boolean;
  add: (username: string) => Promise<void>;
  remove: (username: string) => Promise<void>;
  markSeen: (username: string) => Promise<void>;
  reload: () => Promise<void>;
}

export function useWatchlist(): WatchlistApi {
  const [friends, setFriends] = useState<ScoutWatchFriend[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const list = await fetchScoutWatchlist();
      setFriends(list.friends);
      setError(null);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const lower = (s: string) => s.trim().toLowerCase();

  const run = useCallback(async (name: string, action: () => Promise<void>) => {
    setBusy(name);
    setError(null);
    try {
      await action();
    } catch (err) {
      const status = (err as { response?: { status?: number } }).response?.status;
      setError(status === 409 ? "Your watchlist is full (20 friends). Remove someone first." : apiErrorMessage(err));
    } finally {
      setBusy(null);
    }
  }, []);

  return {
    friends,
    loading,
    error,
    busy,
    isWatching: (username) => friends.some((f) => lower(f.username) === lower(username)),
    reload,
    add: (username) =>
      run(username, async () => {
        const friend = await addScoutWatch(username.trim());
        setFriends((prev) => [...prev.filter((f) => lower(f.username) !== lower(friend.username)), friend]);
      }),
    remove: (username) =>
      run(username, async () => {
        await removeScoutWatch(username);
        setFriends((prev) => prev.filter((f) => lower(f.username) !== lower(username)));
      }),
    markSeen: (username) =>
      run(username, async () => {
        const friend = await markScoutWatchSeen(username);
        setFriends((prev) => prev.map((f) => (lower(f.username) === lower(username) ? friend : f)));
      }),
  };
}

/** "Watch {opponent}" toggle for the profile header. */
export function WatchButton({ username, watch }: { username: string; watch: WatchlistApi }) {
  const watching = watch.isWatching(username);
  return (
    <Button
      variant={watching ? "secondary" : "control"}
      size="sm"
      disabled={watch.busy !== null}
      onClick={() => void (watching ? watch.remove(username) : watch.add(username))}
      aria-pressed={watching}
      aria-label={watching ? `Stop watching ${username}` : `Watch ${username}`}
    >
      {watching ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      {watching ? "Watching" : `Watch ${username}`}
    </Button>
  );
}

function FriendRow({
  friend,
  watch,
  onScout,
}: {
  friend: ScoutWatchFriend;
  watch: WatchlistApi;
  onScout: (username: string) => void;
}) {
  const working = watch.busy === friend.username;
  return (
    <li className="rounded-xl border border-app-border bg-app-raised/40 p-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-mono text-sm font-semibold text-app-text">{friend.username}</span>
        {Object.entries(friend.ratings).map(([tc, rating]) => (
          <Badge key={tc} tone="neutral">{`${tc} ${rating}`}</Badge>
        ))}
        {friend.new_games > 0 && <Badge tone="yellow">{`${friend.new_games} new game${friend.new_games === 1 ? "" : "s"}`}</Badge>}
      </div>
      {friend.error && (
        <p className="mt-1 flex items-center gap-1.5 text-xs text-app-warning">
          <AlertTriangle className="h-3 w-3" />
          {friend.error}
        </p>
      )}
      {friend.alerts.length > 0 && (
        <ul className="mt-2 grid gap-1">
          {friend.alerts.map((a, i) => (
            <li key={`${a.kind}-${i}`} className="text-xs text-app-muted">
              {a.message}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 flex flex-wrap gap-2">
        <Button variant="primary" size="sm" onClick={() => onScout(friend.username)} aria-label={`Scout ${friend.username}`}>
          <Crosshair className="h-4 w-4" />
          Scout
        </Button>
        <Button
          variant="control"
          size="sm"
          disabled={working || (friend.new_games === 0 && friend.alerts.length === 0)}
          onClick={() => void watch.markSeen(friend.username)}
          aria-label={`Mark ${friend.username} as seen`}
        >
          <Check className="h-4 w-4" />
          Mark seen
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={working}
          onClick={() => void watch.remove(friend.username)}
          aria-label={`Remove ${friend.username} from watchlist`}
        >
          <Trash2 className="h-4 w-4" />
          Remove
        </Button>
      </div>
    </li>
  );
}

export function FriendsCard({ watch, onScout }: { watch: WatchlistApi; onScout: (username: string) => void }) {
  if (watch.loading) return null;
  if (!watch.friends.length && !watch.error) return null;
  return (
    <Card>
      <CardHeader title="Friends" eyebrow="Watchlist">
        People you keep an eye on. New games and opening changes show up here.
      </CardHeader>
      {watch.error && (
        <p className="mb-3 flex items-start gap-2 text-sm text-app-blunder">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          {watch.error}
        </p>
      )}
      <ul className="grid gap-3 md:grid-cols-2">
        {watch.friends.map((f) => (
          <FriendRow key={f.username} friend={f} watch={watch} onScout={onScout} />
        ))}
      </ul>
      {!watch.friends.length && (
        <p className="flex items-center gap-2 text-sm text-app-faint">
          <Users className="h-4 w-4" /> No friends yet.
        </p>
      )}
    </Card>
  );
}
