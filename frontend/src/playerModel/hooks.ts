// Polling hook for sync progress (Section 8: live progress + persistent banner).
import { useCallback, useEffect, useRef, useState } from "react";
import { getSyncStatus } from "./api";
import type { SyncStatus } from "./types";

const POLL_MS = 2500;
const ACTIVE: SyncStatus["status"][] = ["pending", "running"];

export function isSyncActive(status: SyncStatus | null): boolean {
  return !!status && ACTIVE.includes(status.status);
}

/**
 * Polls /sync-status for a player while a job is pending/running and stops once
 * it reaches a terminal state. Returns the latest status plus a manual refetch.
 */
export function useSyncStatus(playerId: number | null) {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const tick = useCallback(
    async (id: number) => {
      try {
        const { data } = await getSyncStatus(id);
        setStatus(data);
        setError(null);
        if (ACTIVE.includes(data.status)) {
          timer.current = setTimeout(() => tick(id), POLL_MS);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Sync status unavailable.");
        timer.current = setTimeout(() => tick(id), POLL_MS * 2);
      }
    },
    [],
  );

  useEffect(() => {
    stop();
    setStatus(null);
    setError(null);
    if (playerId == null) return;
    tick(playerId);
    return stop;
  }, [playerId, tick, stop]);

  const refetch = useCallback(() => {
    if (playerId != null) {
      stop();
      tick(playerId);
    }
  }, [playerId, tick, stop]);

  return { status, error, refetch };
}
