import { HelpCircle } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { createPortal } from "react-dom";

const WIDTH = 272;

/**
 * A small "?" button that explains a term in plain language. Click (or tap) to
 * open, click anywhere else / press Escape / scroll to close. The popover is
 * fixed-positioned and clamped to the viewport so it never causes overflow.
 */
export function InfoTip({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  const [open, setOpen] = useState(false);
  const [style, setStyle] = useState<CSSProperties>({});
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const popRef = useRef<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    if (!open || !buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    const width = Math.min(WIDTH, window.innerWidth - 16);
    const left = Math.min(Math.max(8, rect.left + rect.width / 2 - width / 2), window.innerWidth - width - 8);
    const below = rect.bottom + 6;
    const fitsBelow = below + 140 < window.innerHeight;
    setStyle(
      fitsBelow
        ? { position: "fixed", left, top: below, width }
        : { position: "fixed", left, bottom: window.innerHeight - rect.top + 6, width },
    );
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function close(event: Event) {
      const target = event.target as Node | null;
      if (target && (popRef.current?.contains(target) || buttonRef.current?.contains(target))) return;
      setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    function onScroll() {
      setOpen(false);
    }
    document.addEventListener("mousedown", close);
    document.addEventListener("touchstart", close);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("touchstart", close);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open]);

  return (
    <span className={`relative inline-flex align-middle normal-case tracking-normal ${className}`}>
      <button
        ref={buttonRef}
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          setOpen((value) => !value);
        }}
        aria-expanded={open}
        aria-label={`What does "${label}" mean?`}
        className="grid h-4 w-4 place-items-center rounded-full text-app-faint transition hover:text-app-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-app-accent/60"
      >
        <HelpCircle className="h-3.5 w-3.5" />
      </button>
      {open &&
        // Portalled to <body> so scroll containers / transformed ancestors can't clip it.
        createPortal(
          <div
            ref={popRef}
            role="tooltip"
            style={style}
            className="z-50 rounded-lg border border-app-borderStrong bg-app-overlay p-3 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-app-muted shadow-pop animate-pop-in"
          >
            <p className="mb-1 text-[13px] font-semibold text-app-text">{label}</p>
            {children}
          </div>,
          document.body,
        )}
    </span>
  );
}

/** Plain-language definitions, shared by every place that shows the term. */
export const GLOSSARY = {
  vsExpected: (
    <>
      How much better or worse they did than their rating says they should. Beating weaker players is expected, so we compare
      their actual score with the score the ratings predict. <b className="text-app-good">Green / minus</b> = they did worse
      than expected (good for you). <b className="text-app-blunder">Red / plus</b> = they did better.
    </>
  ),
  score: (
    <>Points per game from their side: a win is 100%, a draw 50%, a loss 0%. "Exp" is what the ratings predicted.</>
  ),
  familiarity: (
    <>
      How well they know an opening, 0–100. It goes up when they play it often, repeat the same moves deep into the line, and
      play its first ten moves quickly. A "Main weapon" is a line they've clearly prepared.
    </>
  ),
  evalAt12: (
    <>
      Stockfish's verdict on the position after move 12, from their side, in pawns. <b>-0.5</b> means they usually come out of
      the opening half a pawn worse.
    </>
  ),
  clock: (
    <>
      Share of their starting time they spend on this move. Long thinks early in the game usually mean they've left their
      preparation.
    </>
  ),
  steer: <>Positions you can reach with your own moves where they score clearly below what their rating predicts.</>,
  avoid: <>Positions where they score clearly above their rating: lines they know well. Pick something else if you can.</>,
  unsure: (
    <>
      Positions where they don't have a settled answer: they play several different moves, or they think much longer than
      usual. Their preparation tends to end here.
    </>
  ),
  confidence: (
    <>
      Dots show how much data a number rests on: <b className="text-app-good">green</b> 12+ games,{" "}
      <b className="text-app-warning">amber</b> 5–11, <b>grey</b> fewer (treat as a hint).
    </>
  ),
};
