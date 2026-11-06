import { Printer } from "lucide-react";
import { useEffect } from "react";
import type { ReactNode } from "react";
import type { ScoutDeepResult, ScoutingReport } from "../../types";
import { Button } from "../ui/Button";
import { evalText, pct } from "./shared";

const BODY_CLASS = "cr-printing-prep";

export function PrepSheetButton() {
  function print() {
    document.body.classList.add(BODY_CLASS);
    // Let layout settle so the print-only sheet is measured before the dialog opens.
    window.setTimeout(() => window.print(), 50);
  }
  useEffect(() => {
    const clear = () => document.body.classList.remove(BODY_CLASS);
    window.addEventListener("afterprint", clear);
    return () => {
      window.removeEventListener("afterprint", clear);
      clear();
    };
  }, []);
  return (
    <Button variant="control" size="sm" onClick={print} aria-label="Print prep sheet">
      <Printer className="h-4 w-4" />
      Print prep sheet
    </Button>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="prep-section">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

/** Print-only one-page cheat sheet. Hidden on screen; shown by the print CSS in styles.css. */
export function PrepSheet({ report, deep }: { report: ScoutingReport; deep: ScoutDeepResult | null }) {
  const p = report.profile;
  const plan = report.game_plan;
  const refutations = (deep?.refutations ?? []).slice(0, 3);
  const traps = (deep?.lichess_traps ?? []).slice(0, 3);
  const habitInsights = (report.habits?.insights ?? []).slice(0, 4);
  const h2h = report.head_to_head;
  const ratings = Object.entries(p.ratings)
    .map(([tc, r]) => `${tc} ${r}`)
    .join(" · ");

  return (
    <div className="prep-sheet" aria-hidden="true">
      <header>
        <h1>Prep sheet: {report.username}</h1>
        <p>
          {ratings || "unrated"} · {p.games} games read · scores {pct(p.white.score_pct)} as White, {pct(p.black.score_pct)} as Black
        </p>
      </header>

      <div className="prep-cols">
        <Section title="Game plan">
          {[
            ["You are White", plan.you_white],
            ["You are Black", plan.you_black],
            ["General", plan.general],
          ].map(([label, items]) =>
            (items as string[]).length ? (
              <div key={label as string}>
                <h3>{label as string}</h3>
                <ul>
                  {(items as string[]).slice(0, 3).map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              </div>
            ) : null,
          )}
        </Section>

        <div>
          <Section title="Steer into">
            <ul>
              {report.steer_into.slice(0, 5).map((l) => (
                <li key={`${l.opponent_color}-${l.line}`}>
                  <b>{l.line}</b> (they are {l.opponent_color}; {l.games} games, they score {pct(l.score_pct)})
                </li>
              ))}
              {!report.steer_into.length && <li>No clear line.</li>}
            </ul>
          </Section>
          <Section title="Avoid">
            <ul>
              {report.avoid.slice(0, 4).map((l) => (
                <li key={`${l.opponent_color}-${l.line}`}>
                  <b>{l.line}</b> (they are {l.opponent_color}; they score {pct(l.score_pct)})
                </li>
              ))}
              {!report.avoid.length && <li>No clear line.</li>}
            </ul>
          </Section>
        </div>
      </div>

      {refutations.length > 0 && (
        <Section title="Punish their habits">
          <ul>
            {refutations.map((r) => (
              <li key={`${r.opponent_color}-${r.line}-${r.their_move}`}>
                <b>{r.line}</b>: they play {r.their_move} ({pct(r.their_share)}), {r.severity}, best was {r.best_move} ({evalText(r.eval_best_cp)} vs{" "}
                {evalText(r.eval_after_cp)}). You play <b>{r.punish_move}</b> ({r.punish_line.slice(0, 5).join(" ")}).
              </li>
            ))}
          </ul>
        </Section>
      )}

      {traps.length > 0 && (
        <Section title="Traps at their rating">
          <ul>
            {traps.map((t) => (
              <li key={`${t.opponent_color}-${t.line}-${t.trap_move}`}>
                <b>{t.line}</b>: {t.trap_move} is played {pct(t.trap_share)} but scores {pct(t.trap_score_pct)}
                {t.best_move ? ` (better: ${t.best_move})` : ""}.
              </li>
            ))}
          </ul>
        </Section>
      )}

      {habitInsights.length > 0 && (
        <Section title="Habits">
          <ul>
            {habitInsights.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </Section>
      )}

      {h2h && (
        <Section title={`Head to head (${h2h.me})`}>
          <p>
            Record {h2h.wins}-{h2h.draws}-{h2h.losses} in {h2h.games} games; you score {pct(h2h.score_pct)}.
          </p>
        </Section>
      )}
    </div>
  );
}
