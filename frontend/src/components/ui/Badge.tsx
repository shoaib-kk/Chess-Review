import type { MoveClassification } from "../../types";

interface BadgeProps {
  children: string;
  tone?: "neutral" | "blue" | "green" | "yellow" | "orange" | "red";
  className?: string;
}

const toneClasses = {
  neutral: "bg-app-panelSecondary text-app-muted ring-app-border",
  blue: "bg-app-accentSoft text-[#a5b4fc] ring-app-accent/30",
  green: "bg-[#34d39915] text-app-good ring-[#34d39940]",
  yellow: "bg-[#fbbf2415] text-app-warning ring-[#fbbf2440]",
  orange: "bg-[#fb923c15] text-app-mistake ring-[#fb923c40]",
  red: "bg-[#f43f5e15] text-app-blunder ring-[#f43f5e40]",
};

const classificationSymbols: Record<MoveClassification, string> = {
  Excellent: "!",
  Inaccuracy: "?!",
  Mistake: "?",
  Blunder: "??",
};

export function Badge({ children, tone = "neutral", className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${toneClasses[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function ClassificationBadge({ classification }: { classification: MoveClassification }) {
  const tone =
    classification === "Excellent"
      ? "green"
      : classification === "Inaccuracy"
        ? "yellow"
        : classification === "Mistake"
          ? "orange"
          : "red";

  return <Badge tone={tone}>{`${classification} ${classificationSymbols[classification]}`}</Badge>;
}
