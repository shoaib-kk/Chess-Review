import { Swords, Upload } from "lucide-react";
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
          <label className="inline-flex h-9 cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-app-border bg-app-panelSecondary/60 px-3 text-sm font-medium text-app-muted transition hover:bg-app-panelHover hover:text-app-text">
            <Upload className="h-4 w-4" strokeWidth={2} />
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
          className="h-80 w-full resize-y rounded-lg border border-app-border bg-app-panelSecondary p-4 font-mono text-sm leading-6 text-app-text outline-none transition placeholder:text-app-faint focus-visible:ring-2 focus-visible:ring-app-accent/50 focus:border-app-borderStrong"
          value={pgn}
          placeholder={'[Event "Live Chess"]\n1. e4 c6 2. Nc3 d5 ...'}
          onChange={(event) => setPgn(event.target.value)}
        />

        <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="inline-flex items-center gap-1 rounded-lg border border-app-border bg-app-panelSecondary/40 p-1">
            {(["fast", "normal", "deep"] as AnalysisMode[]).map((item) => (
              <button
                key={item}
                className={`h-8 rounded-md px-3 text-xs font-medium capitalize transition ${
                  mode === item ? "bg-app-accentSoft text-app-text" : "text-app-muted hover:bg-app-panelSecondary hover:text-app-text"
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
            <Swords className="h-4 w-4" />
            {loading ? "Analysing..." : "Analyse Game"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
