// Twin gameplay (Section 8): play against a player's digital twin. The board is
// interactive (chess.js for legality); the twin's move comes from the engine
// with a 600-1200ms artificial "thinking" delay, and falls back to a random
// legal move if the engine errors. A post-game modal reports the move-match rate
// and the twin's least-confident (key) moment.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { Loader2, RotateCcw, X } from "lucide-react";
import { Surface } from "../components/ui/Surface";
import { StyleRadar } from "./charts";
import {
  engineErrorMessage,
  getPatterns,
  getProfile,
  twinBacktest,
  twinMove,
} from "./api";
import type { BacktestResult, BehaviouralPattern, ProfileFeatures } from "./types";

const THINK_MIN = 600;
const THINK_MAX = 1200;

interface TwinGameplayProps {
  playerId: number;
  twinName?: string;
  onExit: () => void;
}

interface PlayedMove {
  san: string;
  by: "you" | "twin";
  confidence?: number;
  fallback?: boolean;
}

export function TwinGameplay({ playerId, twinName, onExit }: TwinGameplayProps) {
  const gameRef = useRef(new Chess());
  const [fen, setFen] = useState(gameRef.current.fen());
  const [history, setHistory] = useState<PlayedMove[]>([]);
  const [thinking, setThinking] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [features, setFeatures] = useState<ProfileFeatures | null>(null);
  const [patterns, setPatterns] = useState<BehaviouralPattern[]>([]);
  const [modal, setModal] = useState<{ result: string; backtest: BacktestResult | null; keyMoment: PlayedMove | null } | null>(null);

  const playerColor: "w" | "b" = "w"; // human plays White, twin plays Black

  useEffect(() => {
    getProfile(playerId).then(({ data }) => setFeatures(data.features)).catch(() => undefined);
    getPatterns(playerId).then(({ data }) => setPatterns(data.slice(0, 5))).catch(() => undefined);
  }, [playerId]);

  const finishIfOver = useCallback(
    (moves: PlayedMove[]) => {
      const game = gameRef.current;
      if (!game.isGameOver()) return false;
      const result = game.isCheckmate()
        ? game.turn() === playerColor
          ? "Twin wins by checkmate"
          : "You win by checkmate!"
        : game.isDraw()
        ? "Draw"
        : "Game over";
      const twinMoves = moves.filter((m) => m.by === "twin" && m.confidence != null);
      const keyMoment =
        twinMoves.length > 0
          ? twinMoves.reduce((lo, m) => ((m.confidence ?? 1) < (lo.confidence ?? 1) ? m : lo))
          : null;
      // Best-effort backtest over the played game (auto-skips on engine error).
      twinBacktest(playerId, game.pgn())
        .then(({ data }) => setModal({ result, backtest: data, keyMoment }))
        .catch(() => setModal({ result, backtest: null, keyMoment }));
      return true;
    },
    [playerId],
  );

  const doTwinMove = useCallback(async () => {
    const game = gameRef.current;
    if (game.isGameOver() || game.turn() === playerColor) return;
    setThinking(true);
    setStatus(null);
    const delay = THINK_MIN + Math.random() * (THINK_MAX - THINK_MIN);
    await new Promise((r) => setTimeout(r, delay));

    let san: string | null = null;
    let confidence: number | undefined;
    let fallback = false;
    try {
      const { data } = await twinMove(playerId, game.fen());
      const uci = data.move;
      const move = game.move({
        from: uci.slice(0, 2),
        to: uci.slice(2, 4),
        promotion: uci.slice(4) || undefined,
      });
      san = move.san;
      confidence = data.confidence;
    } catch (err) {
      // Fallback to a random legal move so a game is always playable offline.
      setStatus(`Twin engine unavailable (${engineErrorMessage(err)}) — using fallback.`);
      const legal = game.moves({ verbose: true });
      if (legal.length) {
        const pick = legal[Math.floor(Math.random() * legal.length)];
        san = game.move(pick).san;
        fallback = true;
      }
    }

    setThinking(false);
    if (san) {
      setFen(game.fen());
      setHistory((h) => {
        const next = [...h, { san: san as string, by: "twin" as const, confidence, fallback }];
        finishIfOver(next);
        return next;
      });
    }
  }, [playerId, finishIfOver]);

  function onPieceDrop(source: string, target: string): boolean {
    const game = gameRef.current;
    if (thinking || game.isGameOver() || game.turn() !== playerColor) return false;
    let move;
    try {
      move = game.move({ from: source, to: target, promotion: "q" });
    } catch {
      return false;
    }
    if (!move) return false;
    setFen(game.fen());
    setHistory((h) => {
      const next = [...h, { san: move.san, by: "you" as const }];
      if (!finishIfOver(next)) {
        void doTwinMove();
      }
      return next;
    });
    return true;
  }

  function newGame() {
    gameRef.current = new Chess();
    setFen(gameRef.current.fen());
    setHistory([]);
    setModal(null);
    setStatus(null);
    setThinking(false);
  }

  const canDrag = !thinking && !gameRef.current.isGameOver() && gameRef.current.turn() === playerColor;

  return (
    <div className="grid items-start gap-5 xl:grid-cols-[minmax(420px,1fr)_340px]">
      <Surface className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-app-text">
            Playing {twinName ?? `Twin #${playerId}`}{" "}
            <span className="text-app-subtle">(you are White)</span>
          </h2>
          <button
            onClick={onExit}
            className="rounded-lg p-1.5 text-app-subtle hover:bg-white/[0.04] hover:text-app-text"
            title="Exit"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mx-auto max-w-[520px]">
          <Chessboard
            position={fen}
            onPieceDrop={onPieceDrop}
            arePiecesDraggable={canDrag}
            boardOrientation="white"
            customBoardStyle={{ borderRadius: 10 }}
          />
        </div>
        <div className="mt-3 flex items-center justify-between text-sm">
          <span className="flex items-center gap-2 text-app-muted">
            {thinking && <Loader2 className="h-4 w-4 animate-spin text-app-accent" />}
            {thinking ? "Twin is thinking…" : gameRef.current.isGameOver() ? "Game over" : canDrag ? "Your move" : ""}
          </span>
          <button
            onClick={newGame}
            className="flex items-center gap-1.5 rounded-lg border border-app-border px-3 py-1.5 text-sm text-app-muted hover:bg-white/[0.04]"
          >
            <RotateCcw className="h-3.5 w-3.5" /> New game
          </button>
        </div>
        {status && <p className="mt-2 text-xs text-amber-400">{status}</p>}
      </Surface>

      <div className="grid gap-5">
        <Surface className="p-5">
          <h3 className="mb-3 text-sm font-semibold text-app-text">Twin personality</h3>
          {features ? (
            <StyleRadar features={features} />
          ) : (
            <div className="h-[200px] animate-pulse rounded-lg bg-white/[0.04]" />
          )}
          {patterns.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {patterns.map((p) => (
                <span
                  key={p.pattern_type}
                  title={p.description}
                  className="rounded-full bg-app-accentSoft px-2.5 py-1 text-[11px] text-app-accent"
                >
                  {p.label}
                </span>
              ))}
            </div>
          )}
        </Surface>

        <Surface className="p-5">
          <h3 className="mb-3 text-sm font-semibold text-app-text">Moves</h3>
          <MoveHistory history={history} />
        </Surface>
      </div>

      {modal && (
        <PostGameModal data={modal} onClose={() => setModal(null)} onNewGame={newGame} />
      )}
    </div>
  );
}

function MoveHistory({ history }: { history: PlayedMove[] }) {
  if (history.length === 0) {
    return <p className="text-sm text-app-subtle">No moves yet — make the first move.</p>;
  }
  const rows: { n: number; white?: PlayedMove; black?: PlayedMove }[] = [];
  history.forEach((m, i) => {
    const r = Math.floor(i / 2);
    rows[r] = rows[r] ?? { n: r + 1 };
    if (i % 2 === 0) rows[r].white = m;
    else rows[r].black = m;
  });
  return (
    <div className="max-h-64 overflow-y-auto pr-1 font-mono text-sm">
      {rows.map((r) => (
        <div key={r.n} className="flex gap-2 py-0.5">
          <span className="w-6 text-app-subtle">{r.n}.</span>
          <span className="w-20 text-app-text">{r.white?.san}</span>
          <span className="w-20 text-app-muted">
            {r.black?.san}
            {r.black?.fallback && <span className="ml-1 text-[10px] text-amber-400">⚙</span>}
          </span>
        </div>
      ))}
    </div>
  );
}

function PostGameModal({
  data,
  onClose,
  onNewGame,
}: {
  data: { result: string; backtest: BacktestResult | null; keyMoment: PlayedMove | null };
  onClose: () => void;
  onNewGame: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <Surface className="w-full max-w-md p-6" onClick={(e: React.MouseEvent) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-app-text">{data.result}</h3>
        {data.backtest ? (
          <div className="mt-4 grid grid-cols-2 gap-3">
            <Stat label="Move match rate" value={`${(data.backtest.move_match_rate * 100).toFixed(0)}%`} />
            <Stat label="Top-3 match" value={`${(data.backtest.top3_match_rate * 100).toFixed(0)}%`} />
            <Stat label="Style match" value={`${(data.backtest.style_match_score * 100).toFixed(0)}%`} />
            <Stat label="CPL correlation" value={data.backtest.cpl_correlation.toFixed(2)} />
          </div>
        ) : (
          <p className="mt-3 text-sm text-app-subtle">Match analysis unavailable for this game.</p>
        )}
        {data.keyMoment && (
          <p className="mt-4 rounded-lg bg-app-raised/60 px-3 py-2 text-sm text-app-muted">
            Key moment: the twin's least-confident move was{" "}
            <span className="font-mono text-app-text">{data.keyMoment.san}</span>{" "}
            ({((data.keyMoment.confidence ?? 0) * 100).toFixed(0)}% confidence).
          </p>
        )}
        <div className="mt-6 flex gap-2">
          <button
            onClick={onClose}
            className="h-10 flex-1 rounded-lg border border-app-border text-sm text-app-muted hover:bg-white/[0.04]"
          >
            Close
          </button>
          <button
            onClick={onNewGame}
            className="h-10 flex-1 rounded-lg bg-app-accent text-sm font-medium text-app-bg hover:brightness-110"
          >
            Play again
          </button>
        </div>
      </Surface>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-app-border bg-app-raised/50 px-3 py-2 text-center">
      <p className="text-lg font-semibold text-app-accent">{value}</p>
      <p className="text-[10px] uppercase tracking-wide text-app-subtle">{label}</p>
    </div>
  );
}
