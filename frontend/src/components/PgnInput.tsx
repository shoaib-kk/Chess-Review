import { useState } from "react";

interface PgnInputProps {
  loading: boolean;
  onAnalyze: (pgn: string, depth: number) => void;
}

export function PgnInput({ loading, onAnalyze }: PgnInputProps) {
  const [pgn, setPgn] = useState("");
  const [depth, setDepth] = useState(16);

  const canAnalyze = pgn.trim().length > 0 && !loading;

  return (
    <section className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-4 py-8 lg:px-8">
      <div className="rounded bg-app-panel p-5 shadow-panel">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-50">Load a PGN</h2>
            <p className="text-sm text-slate-400">Paste a game or upload a `.pgn` file to start the review.</p>
          </div>
          <label className="inline-flex cursor-pointer items-center justify-center rounded border border-white/10 bg-slate-900 px-4 py-2 text-sm font-semibold text-slate-100 hover:border-app-accent">
            Upload PGN
            <input
              className="hidden"
              type="file"
              accept=".pgn,text/plain"
              onChange={async (event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                setPgn(await file.text());
              }}
            />
          </label>
        </div>

        <textarea
          className="h-72 w-full resize-y rounded border border-white/10 bg-slate-950 p-4 font-mono text-sm leading-6 text-slate-100 outline-none focus:border-app-accent"
          value={pgn}
          placeholder='[Event "Live Chess"]&#10;1. e4 c6 2. Nc3 d5 ...'
          onChange={(event) => setPgn(event.target.value)}
        />

        <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <label className="flex items-center gap-3 text-sm text-slate-300">
            Depth
            <input
              type="range"
              min={8}
              max={24}
              value={depth}
              onChange={(event) => setDepth(Number(event.target.value))}
              className="accent-app-accent"
            />
            <span className="w-8 text-right font-mono text-slate-100">{depth}</span>
          </label>
          <button
            className="rounded bg-app-accent px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-blue-500/20 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
            disabled={!canAnalyze}
            onClick={() => onAnalyze(pgn.trim(), depth)}
          >
            {loading ? "Analysing..." : "Analyse Game"}
          </button>
        </div>
      </div>
    </section>
  );
}
