import type { ScoutingReport } from "../../types";
import { ChessGlyph } from "../ui/ChessGlyph";
import { pct } from "./shared";
import type { Side } from "./shared";

/**
 * "Which colour will you have?" Everything on the page below is filtered to the
 * answer, so the user only ever sees the half of the report that applies.
 * ``you`` is the USER'S colour (the opponent has the other one).
 */
export function ColourPicker({
  report,
  you,
  onChange,
}: {
  report: ScoutingReport;
  you: Side;
  onChange: (you: Side) => void;
}) {
  const options: Array<{ you: Side; title: string; their: "white" | "black" }> = [
    { you: "white", title: "I'm White", their: "black" },
    { you: "black", title: "I'm Black", their: "white" },
  ];
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-app-text">Which colour will you have?</p>
      <div className="grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Your colour">
        {options.map((option) => {
          const stats = report.profile[option.their];
          const active = you === option.you;
          return (
            <button
              key={option.you}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(option.you)}
              className={`flex items-center gap-4 rounded-2xl border p-4 text-left transition duration-150 ${
                active
                  ? "border-app-accent bg-app-accentSoft shadow-accent"
                  : "border-app-border bg-app-raised/50 hover:border-app-borderStrong hover:bg-app-raised"
              }`}
            >
              <span
                className={`grid h-12 w-12 shrink-0 place-items-center rounded-xl text-3xl ${
                  option.you === "white" ? "bg-[#f0d9b5] text-[#1a1404]" : "bg-[#2a2a30] text-[#f0d9b5] ring-1 ring-white/10"
                }`}
              >
                <ChessGlyph piece="king" />
              </span>
              <span className="min-w-0">
                <span className="block text-base font-semibold text-app-text">{option.title}</span>
                <span className="block text-xs leading-relaxed text-app-muted">
                  {stats.games
                    ? `They've played ${stats.games} games as ${option.their === "white" ? "White" : "Black"}, scoring ${pct(stats.score_pct)}${
                        stats.expected_pct !== null ? ` (expected ${pct(stats.expected_pct)})` : ""
                      }.`
                    : `No games of theirs as ${option.their === "white" ? "White" : "Black"} with these filters.`}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
