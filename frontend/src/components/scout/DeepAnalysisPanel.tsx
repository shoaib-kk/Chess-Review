import { AlertTriangle, Cpu, Play } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { apiErrorMessage, fetchScoutDeep, startScoutDeep } from "../../api/client";
import type { ScoutDeepResult, ScoutDeepStatus, ScoutTimeClass } from "../../types";
import { Button } from "../ui/Button";
import { Card, CardHeader } from "../ui/Card";
import { Fingerprint } from "./Fingerprint";
import { LichessTraps } from "./LichessTraps";
import { Refutations } from "./Refutations";
import type { OpenLine, Side } from "./shared";

export interface ScoutFilters {
  limit: number;
  time_class: ScoutTimeClass;
  rated_only: boolean;
}

const STAGE_LABEL: Record<string, string> = {
  fetching: "Fetching their games",
  refutations: "Checking their habitual opening moves with Stockfish",
  fingerprint: "Analysing recent games move by move",
  lichess: "Checking the Lichess database",
  done: "Finishing up",
};

const POLL_MS = 4000;

interface Props {
  username: string;
  filters: ScoutFilters;
  onOpen: OpenLine;
  /** Lets the page (e.g. the prep sheet) use finished results. */
  onResult?: (result: ScoutDeepResult | null) => void;
  /** Tells the page whether a job is running (for hints elsewhere). */
  onRunningChange?: (running: boolean) => void;
  /** The OPPONENT's colour the user chose to prepare for; lines for the other colour are hidden. */
  focusColor?: Side;
}

/**
 * Mount this with a `key` of username + filters so a change of opponent or filters resets the poll loop.
 */
export function DeepAnalysisPanel({ username, filters, onOpen, onResult, onRunningChange, focusColor }: Props) {
  const [status, setStatus] = useState<ScoutDeepStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const onResultRef = useRef(onResult);
  onResultRef.current = onResult;

  const apply = useCallback((next: ScoutDeepStatus) => {
    setStatus(next);
    onResultRef.current?.(next.state === "done" ? next.result : null);
  }, []);

  // Read any existing job on mount.
  useEffect(() => {
    let cancelled = false;
    fetchScoutDeep(username, filters)
      .then((s) => {
        if (!cancelled) apply(s);
      })
      .catch(() => {
        /* no status yet is fine; the button still works */
      })
      .finally(() => {
        if (!cancelled) setInitialLoading(false);
      });
    return () => {
      cancelled = true;
      onResultRef.current?.(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [username, filters.limit, filters.time_class, filters.rated_only]);

  const running = status?.state === "running";
  const onRunningRef = useRef(onRunningChange);
  onRunningRef.current = onRunningChange;
  useEffect(() => {
    onRunningRef.current?.(running);
  }, [running]);

  // Poll while running.
  useEffect(() => {
    if (!running) return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      fetchScoutDeep(username, filters)
        .then((s) => {
          if (!cancelled) apply(s);
        })
        .catch((err) => {
          if (!cancelled) setError(apiErrorMessage(err));
        });
    }, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, username, filters.limit, filters.time_class, filters.rated_only]);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      apply(await startScoutDeep(username, filters));
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setStarting(false);
    }
  }

  const progress = status?.progress;
  const fraction = progress && progress.total > 0 ? Math.min(1, progress.done / progress.total) : 0;
  const result = status?.state === "done" ? status.result : null;
  const hasResult = !!result;

  return (
    <Card>
      <CardHeader
        title="Deep engine analysis"
        eyebrow="Stockfish + Lichess"
        action={
          <Button
            variant={hasResult ? "secondary" : "primary"}
            size="sm"
            onClick={() => void start()}
            disabled={starting || running || initialLoading}
            aria-label={hasResult ? "Re-run deep analysis" : "Run deep analysis"}
          >
            <Play className="h-4 w-4" />
            {running ? "Running…" : hasResult ? "Re-run" : "Run deep analysis"}
          </Button>
        }
      >
        Stockfish checks the moves they always play, replays about 40 of their recent games to see how they go wrong, and the
        Lichess database looks for traps at their rating. Takes 3–5 minutes; keep browsing the other tabs while it works.
      </CardHeader>

      {error && (
        <div className="mb-4 flex items-start gap-3 rounded-lg bg-app-blunder/10 px-4 py-3 text-sm text-app-blunder ring-1 ring-app-blunder/30">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {running && (
        <div className="mb-4 rounded-lg border border-app-border bg-app-panelSecondary p-4" role="status" aria-live="polite">
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className="flex min-w-0 items-center gap-2 text-app-text">
              <Cpu className="h-4 w-4 shrink-0 animate-pulse text-app-accent" />
              <span className="truncate">{STAGE_LABEL[status?.stage ?? ""] ?? "Working"}</span>
            </span>
            <span className="nums shrink-0 text-xs text-app-muted">
              {progress && progress.total > 0 ? `${progress.done} / ${progress.total}` : "starting"}
            </span>
          </div>
          <div
            className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/5"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(fraction * 100)}
            aria-label="Deep analysis progress"
          >
            <div className="h-full rounded-full bg-app-accent transition-[width] duration-500" style={{ width: `${Math.max(3, fraction * 100)}%` }} />
          </div>
        </div>
      )}

      {status?.state === "error" && (
        <div className="mb-4 flex items-start gap-3 rounded-lg bg-app-blunder/10 px-4 py-3 text-sm text-app-blunder ring-1 ring-app-blunder/30">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>The analysis failed{status.error ? `: ${status.error}` : "."} You can run it again.</span>
        </div>
      )}

      {!result && !running && status?.state !== "error" && (
        <p className="rounded-lg border border-dashed border-app-border px-4 py-6 text-center text-sm text-app-faint">
          {initialLoading ? "Checking for earlier results…" : "No deep analysis yet for this opponent and these filters."}
        </p>
      )}

      {result && (
        <div className="grid gap-8">
          {focusColor && (
            <p className="-mb-4 text-xs text-app-faint">
              Showing opening lines for when you have {focusColor === "white" ? "Black" : "White"}. Switch colour at the top to see
              the others.
            </p>
          )}
          <Refutations
            items={focusColor ? result.refutations.filter((r) => r.opponent_color === focusColor) : result.refutations}
            onOpen={onOpen}
          />
          <Fingerprint data={result.fingerprint} />
          <LichessTraps
            traps={
              result.lichess_traps && focusColor
                ? result.lichess_traps.filter((t) => t.opponent_color === focusColor)
                : result.lichess_traps
            }
            error={result.lichess_error}
            onOpen={onOpen}
          />
          <p className="text-[11px] text-app-faint">Generated {new Date(result.generated_at).toLocaleString()}</p>
        </div>
      )}
    </Card>
  );
}
