// Container for the Player Modelling surfaces (Section 8). Owns the active
// player (persisted to localStorage so a refresh resumes), routes between
// onboarding / profile / twin, and renders the persistent sync banner.
import { useEffect, useState } from "react";
import { Loader2, UserPlus } from "lucide-react";
import { Surface } from "../components/ui/Surface";
import { Onboarding } from "./Onboarding";
import { ProfileDashboard } from "./ProfileDashboard";
import { TwinGameplay } from "./TwinGameplay";
import { connectChessCom, getSyncStatus } from "./api";
import { isSyncActive, useSyncStatus } from "./hooks";

type Screen = "onboarding" | "profile" | "twin";
const PLAYER_KEY = "pm_player_id";

function loadPlayerId(): number | null {
  const raw = localStorage.getItem(PLAYER_KEY);
  const n = raw ? Number(raw) : NaN;
  return Number.isFinite(n) && n > 0 ? n : null;
}

export function PlayerModelApp() {
  const [playerId, setPlayerId] = useState<number | null>(loadPlayerId);
  const [screen, setScreen] = useState<Screen>(playerId ? "profile" : "onboarding");
  const { status } = useSyncStatus(playerId);

  useEffect(() => {
    if (playerId != null) localStorage.setItem(PLAYER_KEY, String(playerId));
    else localStorage.removeItem(PLAYER_KEY);
  }, [playerId]);

  function handlePlayerReady(pid: number) {
    setPlayerId(pid);
  }

  function switchPlayer() {
    setPlayerId(null);
    setScreen("onboarding");
  }

  async function handleResync(pid: number) {
    try {
      const { data } = await getSyncStatus(pid);
      await connectChessCom(pid, {
        chess_com_username: data.chess_com_username ?? undefined,
      });
    } catch {
      // Banner will surface failures via the next poll.
    }
  }

  const bannerVisible = screen !== "onboarding" && isSyncActive(status);

  return (
    <div className="grid gap-4">
      {/* Tabs + player switch */}
      {playerId != null && (
        <div className="flex items-center justify-between">
          <div className="flex gap-1">
            <Tab active={screen === "profile"} onClick={() => setScreen("profile")}>
              Profile
            </Tab>
            <Tab active={screen === "twin"} onClick={() => setScreen("twin")}>
              Play twin
            </Tab>
          </div>
          <button
            onClick={switchPlayer}
            className="flex items-center gap-1.5 rounded-lg border border-app-border px-3 py-1.5 text-sm text-app-muted transition hover:bg-white/[0.04]"
          >
            <UserPlus className="h-4 w-4" /> New player
          </button>
        </div>
      )}

      {bannerVisible && status && (
        <Surface className="flex items-center gap-3 p-3">
          <Loader2 className="h-4 w-4 animate-spin text-app-accent" />
          <span className="text-sm text-app-muted">
            Syncing {status.chess_com_username}…{" "}
            {status.total_games > 0
              ? `${status.processed_games}/${status.total_games} games`
              : "fetching archives"}
          </span>
          <div className="ml-auto h-1.5 w-40 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              className="h-full rounded-full bg-app-accent transition-[width]"
              style={{
                width:
                  status.total_games > 0
                    ? `${Math.round((status.processed_games / status.total_games) * 100)}%`
                    : "33%",
              }}
            />
          </div>
        </Surface>
      )}

      {screen === "onboarding" && (
        <Onboarding
          onPlayerReady={handlePlayerReady}
          onOpenProfile={(pid) => {
            setPlayerId(pid);
            setScreen("profile");
          }}
          onPlayTwin={(pid) => {
            setPlayerId(pid);
            setScreen("twin");
          }}
        />
      )}

      {screen === "profile" && playerId != null && (
        <ProfileDashboard
          playerId={playerId}
          onPlayTwin={() => setScreen("twin")}
          onResync={handleResync}
        />
      )}

      {screen === "twin" && playerId != null && (
        <TwinGameplay
          playerId={playerId}
          twinName={status?.chess_com_username ?? undefined}
          onExit={() => setScreen("profile")}
        />
      )}
    </div>
  );
}

function Tab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg px-4 py-1.5 text-sm font-medium transition ${
        active ? "bg-app-accentSoft text-app-accent" : "text-app-muted hover:bg-white/[0.04]"
      }`}
    >
      {children}
    </button>
  );
}
