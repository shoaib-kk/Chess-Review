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
  const [mode, setMode] = useState<AnalysisMode>("normal");

  const canAnalyze = pgn.trim().length > 0 && !loading;
  const modeDepth: Record<AnalysisMode, number> = { fast: 10, normal: 16, deep: 22 };
  const modeLabels: Record<AnalysisMode, { label: string; help: string }> = {
    fast: { label: "Quick look", help: "Fastest" },
    normal: { label: "Standard", help: "Balanced" },
    deep: { label: "Thorough", help: "Slower" },
  };

  return (
    <Card>
      <CardHeader title="Paste or upload a game" eyebrow="Manual review">
        Paste a PGN from Chess.com, Lichess, or an over-the-board game. No username needed.
      </CardHeader>

      <div>
        <div className="mb-3 flex justify-end">
          <label className="inline-flex h-9 cursor-pointer items-center justify-center gap-1.5 rounded-lg border border-app-border bg-app-panelSecondary px-3 text-sm font-medium text-app-muted transition hover:bg-app-panelHover hover:text-app-text">
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
          <div className="inline-flex items-center gap-1 rounded-lg border border-app-border bg-app-panelSecondary p-1">
            {(["fast", "normal", "deep"] as AnalysisMode[]).map((item) => (
              <button
                key={item}
                title={modeLabels[item].help}
                className={`h-9 rounded-md px-3 text-xs font-medium transition ${
                  mode === item ? "bg-app-accentSoft text-app-text" : "text-app-muted hover:bg-app-panelSecondary hover:text-app-text"
                }`}
                onClick={() => setMode(item)}
              >
                {modeLabels[item].label}
              </button>
            ))}
          </div>
          <Button variant="primary" disabled={!canAnalyze} onClick={() => onAnalyze(pgn.trim(), modeDepth[mode], mode)}>
            <Swords className="h-4 w-4" />
            {loading ? "Analyzing..." : "Analyze Game"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
