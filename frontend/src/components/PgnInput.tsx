import { useState } from "react";
import type { AnalysisMode } from "../types";
import { Button } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";

interface PgnInputProps {
  loading: boolean;
  onAnalyze: (pgn: string, depth: number, mode: AnalysisMode) => void;
}

export function PgnInput({ loading, onAnalyze }: PgnInputProps) {
  const [pgn, setPgn] = useState("");
  const [depth, setDepth] = useState(16);
  const [mode, setMode] = useState<AnalysisMode>("normal");

  const canAnalyze = pgn.trim().length > 0 && !loading;

  return (
    <Card className="overflow-hidden">
      <CardHeader title="Paste or upload PGN" eyebrow="Manual review">
        Load any PGN and run the same Stockfish review flow.
      </CardHeader>

      <div className="px-5 pb-5">
        <div className="mb-3 flex justify-end">
          <label className="inline-flex h-10 cursor-pointer items-center justify-center rounded-md bg-app-panelSecondary px-3 text-sm font-semibold text-app-text transition hover:bg-slate-700">
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
          className="h-80 w-full resize-y rounded-md bg-slate-950/80 p-4 font-mono text-sm leading-6 text-app-text outline-none ring-1 ring-app-border transition placeholder:text-slate-600 focus:ring-2 focus:ring-app-accent/70"
          value={pgn}
          placeholder={'[Event "Live Chess"]\n1. e4 c6 2. Nc3 d5 ...'}
          onChange={(event) => setPgn(event.target.value)}
        />

        <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2 rounded-md bg-slate-950/60 p-1 ring-1 ring-app-border">
            {(["fast", "normal", "deep"] as AnalysisMode[]).map((item) => (
              <button
                key={item}
                className={`h-8 rounded px-3 text-xs font-bold capitalize transition ${
                  mode === item ? "bg-app-accent text-white" : "text-app-muted hover:bg-app-panelSecondary hover:text-app-text"
                }`}
                onClick={() => setMode(item)}
              >
                {item}
              </button>
            ))}
          </div>

          <label className="flex items-center gap-3 text-sm text-app-muted">
            Depth
            <input
              type="range"
              min={8}
              max={24}
              value={depth}
              onChange={(event) => setDepth(Number(event.target.value))}
              className="accent-app-accent"
            />
            <span className="w-8 text-right font-mono text-app-text">{depth}</span>
          </label>
          <Button variant="primary" disabled={!canAnalyze} onClick={() => onAnalyze(pgn.trim(), depth, mode)}>
            {loading ? "Analysing..." : "Analyse Game"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
