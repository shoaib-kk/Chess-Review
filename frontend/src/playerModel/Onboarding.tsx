// Onboarding (Section 8): username + time control -> avatar confirmation ->
// live sync progress -> reveal archetype + top patterns + CTAs.
import { useEffect, useState } from "react";
import { Check, Loader2, Sparkles, Swords, User } from "lucide-react";
import { Surface } from "../components/ui/Surface";
import {
  connectChessCom,
  createPlayer,
  engineErrorCode,
  engineErrorMessage,
  getChessComProfile,
  getPatterns,
  getProfile,
} from "./api";
import { useSyncStatus, isSyncActive } from "./hooks";
import type { BehaviouralPattern, ChessComProfile } from "./types";

const TIME_CONTROLS = [
  { id: "bullet", label: "Bullet" },
  { id: "blitz", label: "Blitz" },
  { id: "rapid", label: "Rapid" },
];

type Step = "enter" | "confirm" | "syncing" | "reveal";

interface OnboardingProps {
  onPlayerReady: (playerId: number) => void;
  onOpenProfile: (playerId: number) => void;
  onPlayTwin: (playerId: number) => void;
}

export function Onboarding({ onPlayerReady, onOpenProfile, onPlayTwin }: OnboardingProps) {
  const [step, setStep] = useState<Step>("enter");
  const [username, setUsername] = useState("");
  const [timeClasses, setTimeClasses] = useState<string[]>(["blitz", "rapid"]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [playerId, setPlayerId] = useState<number | null>(null);
  const [ccProfile, setCcProfile] = useState<ChessComProfile | null>(null);

  const { status } = useSyncStatus(step === "syncing" ? playerId : null);

  // Advance to the reveal once the background sync finishes.
  useEffect(() => {
    if (step === "syncing" && status && !isSyncActive(status)) {
      if (status.status === "failed") {
        setError(status.error_log || "Sync failed. Please try again.");
      }
      setStep("reveal");
    }
  }, [step, status]);

  function toggleTimeClass(id: string) {
    setTimeClasses((prev) => (prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]));
  }

  async function handleLookup() {
    const uname = username.trim();
    if (!uname) return;
    setBusy(true);
    setError(null);
    try {
      const { data } = await getChessComProfile(uname);
      setCcProfile(data);
      setStep("confirm");
    } catch (err) {
      setError(engineErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleConnect() {
    setBusy(true);
    setError(null);
    try {
      const created = await createPlayer(username.trim());
      const pid = created.data.player_id;
      setPlayerId(pid);
      onPlayerReady(pid);
      await connectChessCom(pid, {
        chess_com_username: username.trim(),
        time_classes: timeClasses.length ? timeClasses : undefined,
      });
      setStep("syncing");
    } catch (err) {
      setError(engineErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl py-4">
      <Stepper step={step} />
      {error && (
        <div className="mb-4 rounded-lg bg-app-blunder/10 px-4 py-3 text-sm text-app-blunder ring-1 ring-app-blunder/30">
          {error}
        </div>
      )}

      {step === "enter" && (
        <Surface className="p-6">
          <h2 className="text-lg font-semibold text-app-text">Build your digital twin</h2>
          <p className="mt-1 text-sm text-app-muted">
            Enter your Chess.com username — we'll analyse your games and learn how you play.
          </p>
          <label className="mt-5 block text-xs font-medium uppercase tracking-wide text-app-subtle">
            Chess.com username
          </label>
          <div className="mt-1.5 flex items-center gap-2 rounded-lg border border-app-border bg-app-raised/60 px-3">
            <User className="h-4 w-4 text-app-faint" />
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLookup()}
              placeholder="e.g. hikaru"
              className="h-11 flex-1 bg-transparent text-sm text-app-text outline-none placeholder:text-app-faint"
            />
          </div>

          <p className="mt-5 text-xs font-medium uppercase tracking-wide text-app-subtle">
            Time controls to model
          </p>
          <div className="mt-1.5 flex gap-2">
            {TIME_CONTROLS.map((tc) => {
              const on = timeClasses.includes(tc.id);
              return (
                <button
                  key={tc.id}
                  onClick={() => toggleTimeClass(tc.id)}
                  className={`flex-1 rounded-lg border px-3 py-2 text-sm transition ${
                    on
                      ? "border-app-accentLine bg-app-accentSoft text-app-text"
                      : "border-app-border text-app-muted hover:bg-white/[0.04]"
                  }`}
                >
                  {tc.label}
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-[11px] text-app-subtle">Daily (correspondence) games are always excluded.</p>

          <button
            onClick={handleLookup}
            disabled={busy || !username.trim()}
            className="mt-6 flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-app-accent font-medium text-app-bg transition hover:brightness-110 disabled:opacity-50"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Continue"}
          </button>
        </Surface>
      )}

      {step === "confirm" && ccProfile && (
        <Surface className="p-6 text-center">
          <h2 className="text-lg font-semibold text-app-text">Is this you?</h2>
          <div className="mt-5 flex flex-col items-center gap-3">
            <img
              src={ccProfile.avatar ?? undefined}
              alt={ccProfile.username ?? "avatar"}
              className="h-20 w-20 rounded-full border border-app-border bg-app-raised object-cover"
              onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")}
            />
            <div>
              <p className="font-mono text-base font-semibold text-app-text">{ccProfile.username}</p>
              {ccProfile.name && <p className="text-sm text-app-muted">{ccProfile.name}</p>}
            </div>
          </div>
          <div className="mt-6 flex gap-2">
            <button
              onClick={() => setStep("enter")}
              className="h-11 flex-1 rounded-lg border border-app-border text-sm text-app-muted transition hover:bg-white/[0.04]"
            >
              Not me
            </button>
            <button
              onClick={handleConnect}
              disabled={busy}
              className="flex h-11 flex-1 items-center justify-center gap-2 rounded-lg bg-app-accent text-sm font-medium text-app-bg transition hover:brightness-110 disabled:opacity-50"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Connect & analyse"}
            </button>
          </div>
        </Surface>
      )}

      {step === "syncing" && (
        <Surface className="p-6">
          <div className="flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-app-accent" />
            <h2 className="text-lg font-semibold text-app-text">Analysing your games…</h2>
          </div>
          <p className="mt-1 text-sm text-app-muted">
            Running every position through Stockfish. This can take a while on the first sync —
            you can keep this tab open.
          </p>
          <SyncProgress
            processed={status?.processed_games ?? 0}
            total={status?.total_games ?? 0}
          />
        </Surface>
      )}

      {step === "reveal" && playerId != null && (
        <Reveal playerId={playerId} onOpenProfile={onOpenProfile} onPlayTwin={onPlayTwin} />
      )}
    </div>
  );
}

function SyncProgress({ processed, total }: { processed: number; total: number }) {
  const pct = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
  return (
    <div className="mt-5">
      <div className="mb-1.5 flex justify-between text-xs text-app-subtle">
        <span>{total > 0 ? `${processed} / ${total} games` : "Fetching archives…"}</span>
        <span>{total > 0 ? `${pct}%` : ""}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className={`h-full rounded-full bg-app-accent transition-[width] duration-500 ${
            total === 0 ? "w-1/3 animate-pulse" : ""
          }`}
          style={total > 0 ? { width: `${pct}%` } : undefined}
        />
      </div>
    </div>
  );
}

function Reveal({
  playerId,
  onOpenProfile,
  onPlayTwin,
}: {
  playerId: number;
  onOpenProfile: (id: number) => void;
  onPlayTwin: (id: number) => void;
}) {
  const [archetype, setArchetype] = useState<string | null>(null);
  const [patterns, setPatterns] = useState<BehaviouralPattern[]>([]);
  const [notReady, setNotReady] = useState<string | null>(null);

  useEffect(() => {
    getProfile(playerId)
      .then(({ data }) => setArchetype(data.archetype))
      .catch((err) => {
        const code = engineErrorCode(err);
        if (code === "INSUFFICIENT_GAMES" || code === "PROFILE_NOT_READY") {
          setNotReady(engineErrorMessage(err));
        }
      });
    getPatterns(playerId)
      .then(({ data }) => setPatterns(data.slice(0, 3)))
      .catch(() => undefined);
  }, [playerId]);

  return (
    <Surface className="p-6 text-center">
      <Sparkles className="mx-auto h-8 w-8 text-app-accent" />
      <h2 className="mt-3 text-lg font-semibold text-app-text">Your twin is ready</h2>
      {notReady ? (
        <p className="mt-2 text-sm text-app-muted">{notReady}</p>
      ) : (
        <>
          <p className="mt-1 text-sm text-app-muted">We classified your style as</p>
          <p className="mt-2 text-2xl font-bold text-app-accent">{archetype ?? "All-Rounder"}</p>
        </>
      )}

      {patterns.length > 0 && (
        <div className="mt-5 text-left">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-app-subtle">
            Top tendencies
          </p>
          <ul className="space-y-1.5">
            {patterns.map((p) => (
              <li key={p.pattern_type} className="flex items-center gap-2 text-sm text-app-muted">
                <Check className="h-4 w-4 shrink-0 text-app-accent" />
                {p.label}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-6 flex gap-2">
        <button
          onClick={() => onOpenProfile(playerId)}
          className="h-11 flex-1 rounded-lg border border-app-border text-sm font-medium text-app-text transition hover:bg-white/[0.04]"
        >
          View profile
        </button>
        <button
          onClick={() => onPlayTwin(playerId)}
          className="flex h-11 flex-1 items-center justify-center gap-2 rounded-lg bg-app-accent text-sm font-medium text-app-bg transition hover:brightness-110"
        >
          <Swords className="h-4 w-4" /> Play your twin
        </button>
      </div>
    </Surface>
  );
}

function Stepper({ step }: { step: Step }) {
  const order: Step[] = ["enter", "confirm", "syncing", "reveal"];
  const idx = order.indexOf(step);
  const labels = ["Account", "Confirm", "Analyse", "Ready"];
  return (
    <div className="mb-6 flex items-center justify-center gap-2">
      {labels.map((label, i) => (
        <div key={label} className="flex items-center gap-2">
          <div
            className={`flex h-7 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition ${
              i <= idx ? "bg-app-accentSoft text-app-accent" : "bg-white/[0.04] text-app-subtle"
            }`}
          >
            {i < idx ? <Check className="h-3.5 w-3.5" /> : <span>{i + 1}</span>}
            {label}
          </div>
          {i < labels.length - 1 && <span className="h-px w-4 bg-app-border" />}
        </div>
      ))}
    </div>
  );
}
