import type { MoveClassification } from "../types";

export type BadgeTone = "neutral" | "blue" | "green" | "yellow" | "orange" | "red";

export interface ClassificationMeta {
  /** Human label (same as the classification key). */
  label: MoveClassification;
  /** Symbol shown in the move-list / badge (e.g. "??"). */
  badgeSymbol: string;
  /** Symbol drawn on the board; empty string = no on-board annotation. */
  boardSymbol: string;
  /** Hex colour for the eval-graph dot and board annotation chip. */
  color: string;
  /** Badge colour tone. */
  tone: BadgeTone;
  /** Tailwind text colour class for the move-list row. */
  textClass: string;
  /** Inline style for the on-board annotation chip. */
  annotation: { backgroundColor: string; color: string };
  /** A notable error (drives board annotation + eval-graph emphasis). */
  isError: boolean;
  /** A positive standout (Brilliant) worth highlighting. */
  isHighlight: boolean;
}

const TRANSPARENT = { backgroundColor: "transparent", color: "inherit" };

export const CLASSIFICATION_META: Record<MoveClassification, ClassificationMeta> = {
  Book: {
    label: "Book",
    badgeSymbol: "",
    boardSymbol: "",
    color: "#94a3b8",
    tone: "neutral",
    textClass: "text-app-muted",
    annotation: TRANSPARENT,
    isError: false,
    isHighlight: false,
  },
  Brilliant: {
    label: "Brilliant",
    badgeSymbol: "!!",
    boardSymbol: "!!",
    color: "#2cc7b8",
    tone: "blue",
    textClass: "text-[#5fd6c9]",
    annotation: { backgroundColor: "#2cc7b8", color: "#04201d" },
    isError: false,
    isHighlight: true,
  },
  // The critical "only move" — found the best move when alternatives were much
  // worse. Blue, distinct from Brilliant's teal and the green positive family.
  Great: {
    label: "Great",
    badgeSymbol: "!",
    boardSymbol: "!",
    color: "#5b8def",
    tone: "blue",
    textClass: "text-[#8ab0ff]",
    annotation: { backgroundColor: "#5b8def", color: "#04132e" },
    isError: false,
    isHighlight: true,
  },
  // Best / Excellent / Good share one green family — a single positive hue
  // rather than three competing greens.
  Best: {
    label: "Best",
    badgeSymbol: "★",
    boardSymbol: "",
    color: "#56b277",
    tone: "green",
    textClass: "text-app-good",
    annotation: TRANSPARENT,
    isError: false,
    isHighlight: false,
  },
  Excellent: {
    label: "Excellent",
    badgeSymbol: "!",
    boardSymbol: "",
    color: "#56b277",
    tone: "green",
    textClass: "text-app-good",
    annotation: TRANSPARENT,
    isError: false,
    isHighlight: false,
  },
  Good: {
    label: "Good",
    badgeSymbol: "",
    boardSymbol: "",
    color: "#8b9099",
    tone: "neutral",
    textClass: "text-app-text",
    annotation: TRANSPARENT,
    isError: false,
    isHighlight: false,
  },
  Inaccuracy: {
    label: "Inaccuracy",
    badgeSymbol: "?!",
    boardSymbol: "?!",
    color: "#d6b24a",
    tone: "yellow",
    textClass: "text-app-warning",
    annotation: { backgroundColor: "#d6b24a", color: "#211a05" },
    isError: true,
    isHighlight: false,
  },
  // Mistake and Miss share one orange — same severity tier, one hue.
  Mistake: {
    label: "Mistake",
    badgeSymbol: "?",
    boardSymbol: "?",
    color: "#d9863e",
    tone: "orange",
    textClass: "text-app-mistake",
    annotation: { backgroundColor: "#d9863e", color: "#241404" },
    isError: true,
    isHighlight: false,
  },
  Miss: {
    label: "Miss",
    badgeSymbol: "✗",
    boardSymbol: "✗",
    color: "#d9863e",
    tone: "orange",
    textClass: "text-app-mistake",
    annotation: { backgroundColor: "#d9863e", color: "#241404" },
    isError: true,
    isHighlight: false,
  },
  Blunder: {
    label: "Blunder",
    badgeSymbol: "??",
    boardSymbol: "??",
    color: "#d9574f",
    tone: "red",
    textClass: "text-app-blunder",
    annotation: { backgroundColor: "#d9574f", color: "#ffffff" },
    isError: true,
    isHighlight: false,
  },
};

export function classificationMeta(classification: MoveClassification): ClassificationMeta {
  // Fall back to Excellent styling for any unexpected value from older payloads.
  return CLASSIFICATION_META[classification] ?? CLASSIFICATION_META.Excellent;
}
