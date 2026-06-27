// Profile dashboard (Section 8): header, style radar, accuracy-by-phase,
// behavioural pattern cards, opening treemap, weakness heatmap. Skeleton loaders
// while the profile is being computed.
import { useEffect, useState } from "react";
import { RefreshCw, Swords } from "lucide-react";
import { Surface } from "../components/ui/Surface";
import {
  AccuracyByPhase,
  OpeningTreemap,
  StyleRadar,
  TradePreferenceBars,
} from "./charts";
import { PatternCard, WeaknessBoard } from "./PatternCards";
import {
  engineErrorCode,
  engineErrorMessage,
  getPatterns,
  getProfile,
  getStyleVector,
  getSyncStatus,
} from "./api";
import type {
  BehaviouralPattern,
  ProfileResponse,
  StyleVectorResponse,
  SyncStatus,
} from "./types";

interface ProfileDashboardProps {
  playerId: number;
  onPlayTwin: (playerId: number) => void;
  onResync: (playerId: number) => void;
}

export function ProfileDashboard({ playerId, onPlayTwin, onResync }: ProfileDashboardProps) {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [patterns, setPatterns] = useState<BehaviouralPattern[]>([]);
  const [style, setStyle] = useState<StyleVectorResponse | null>(null);
  const [sync, setSync] = useState<SyncStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [notReady, setNotReady] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setNotReady(null);

    getSyncStatus(playerId).then(({ data }) => !cancelled && setSync(data)).catch(() => undefined);
    getPatterns(playerId).then(({ data }) => !cancelled && setPatterns(data)).catch(() => undefined);
    getStyleVector(playerId).then(({ data }) => !cancelled && setStyle(data)).catch(() => undefined);

    getProfile(playerId)
      .then(({ data }) => {
        if (!cancelled) setProfile(data);
      })
      .catch((err) => {
        if (cancelled) return;
        const code = engineErrorCode(err);
        if (code === "INSUFFICIENT_GAMES" || code === "PROFILE_NOT_READY") {
          setNotReady(engineErrorMessage(err));
        } else {
          setNotReady(engineErrorMessage(err));
        }
      })
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
  }, [playerId]);

  const features = profile?.features;

  return (
    <div className="grid gap-5">
      <ProfileHeader
        sync={sync}
        archetype={profile?.archetype ?? null}
        onPlayTwin={() => onPlayTwin(playerId)}
        onResync={() => onResync(playerId)}
      />

      {loading ? (
        <SkeletonGrid />
      ) : notReady && !features ? (
        <Surface className="p-8 text-center">
          <p className="text-sm text-app-muted">{notReady}</p>
          <button
            onClick={() => onResync(playerId)}
            className="mt-4 inline-flex h-10 items-center gap-2 rounded-lg border border-app-border px-4 text-sm text-app-text hover:bg-white/[0.04]"
          >
            <RefreshCw className="h-4 w-4" /> Sync more games
          </button>
        </Surface>
      ) : (
        features && (
          <>
            <div className="grid gap-5 lg:grid-cols-2">
              <Card title="Style profile" subtitle={profile?.archetype ?? undefined}>
                <StyleRadar features={features} />
              </Card>
              <Card title="Accuracy by phase">
                <AccuracyByPhase features={features} />
              </Card>
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              <Card title="Opening repertoire" subtitle="by ECO code">
                <OpeningTreemap ecoDistribution={features.opening.eco_distribution} />
              </Card>
              <Card title="Trade tendencies" subtitle="how often you keep vs trade each piece">
                <TradePreferenceBars prefs={features.style.trade_preference_by_piece} />
                <StatRow features={features} />
              </Card>
            </div>

            {patterns.length > 0 && (
              <Card title="Behavioural patterns" subtitle={`${patterns.length} detected`}>
                <div className="grid gap-3 sm:grid-cols-2">
                  {patterns.map((p) => (
                    <PatternCard key={p.pattern_type} pattern={p} />
                  ))}
                </div>
              </Card>
            )}

            <Card title="Weakness heatmap" subtitle="where your mistakes cluster">
              <WeaknessBoard patterns={patterns} />
            </Card>

            {style?.similar_players && style.similar_players.length > 0 && (
              <Card title="Similar players">
                <div className="flex flex-wrap gap-2">
                  {style.similar_players.map((s) => (
                    <span
                      key={s.player_id}
                      className="rounded-full border border-app-border bg-app-raised/60 px-3 py-1 text-sm text-app-muted"
                    >
                      {s.username}
                      {s.archetype && <span className="ml-1.5 text-xs text-app-subtle">· {s.archetype}</span>}
                    </span>
                  ))}
                </div>
              </Card>
            )}
          </>
        )
      )}
    </div>
  );
}

function ProfileHeader({
  sync,
  archetype,
  onPlayTwin,
  onResync,
}: {
  sync: SyncStatus | null;
  archetype: string | null | undefined;
  onPlayTwin: () => void;
  onResync: () => void;
}) {
  return (
    <Surface className="flex flex-wrap items-center gap-4 p-5">
      <img
        src={sync?.avatar_url ?? undefined}
        alt="avatar"
        className="h-14 w-14 rounded-full border border-app-border bg-app-raised object-cover"
        onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")}
      />
      <div className="min-w-0 flex-1">
        <h1 className="truncate font-mono text-lg font-semibold text-app-text">
          {sync?.chess_com_username ?? "Player"}
        </h1>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-app-subtle">
          {archetype && <span className="text-app-accent">{archetype}</span>}
          <span>{sync?.game_count ?? 0} games analysed</span>
          {sync?.last_synced_at && (
            <span>synced {new Date(sync.last_synced_at).toLocaleDateString()}</span>
          )}
        </div>
      </div>
      <div className="flex gap-2">
        <button
          onClick={onResync}
          title="Sync newer games"
          className="flex h-10 items-center gap-2 rounded-lg border border-app-border px-3 text-sm text-app-muted transition hover:bg-white/[0.04]"
        >
          <RefreshCw className="h-4 w-4" /> Resync
        </button>
        <button
          onClick={onPlayTwin}
          className="flex h-10 items-center gap-2 rounded-lg bg-app-accent px-4 text-sm font-medium text-app-bg transition hover:brightness-110"
        >
          <Swords className="h-4 w-4" /> Play twin
        </button>
      </div>
    </Surface>
  );
}

function StatRow({ features }: { features: ProfileResponse["features"] }) {
  const stats = [
    { label: "Mean CPL", value: features.accuracy.mean_cpl?.toFixed(0) ?? "—" },
    { label: "Blunders/10", value: features.accuracy.blunder_rate?.toFixed(2) ?? "—" },
    { label: "Brilliant rate", value: pct(features.tactical.brilliant_move_rate) },
    { label: "Repertoire", value: features.opening.opening_repertoire_size ?? "—" },
  ];
  return (
    <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
      {stats.map((s) => (
        <div key={s.label} className="rounded-lg border border-app-border bg-app-raised/50 px-3 py-2 text-center">
          <p className="text-base font-semibold text-app-text">{s.value}</p>
          <p className="text-[10px] uppercase tracking-wide text-app-subtle">{s.label}</p>
        </div>
      ))}
    </div>
  );
}

function pct(v: number | null | undefined): string {
  return v == null ? "—" : `${(v * 100).toFixed(1)}%`;
}

function Card({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <Surface className="p-5">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-app-text">{title}</h3>
        {subtitle && <p className="text-xs text-app-subtle">{subtitle}</p>}
      </div>
      {children}
    </Surface>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Surface key={i} className="p-5">
          <div className="mb-3 h-4 w-32 animate-pulse rounded bg-white/[0.06]" />
          <div className="h-[220px] animate-pulse rounded-lg bg-white/[0.04]" />
        </Surface>
      ))}
    </div>
  );
}
