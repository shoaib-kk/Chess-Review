import type { MoveClassification } from "../../types";

interface BadgeProps {
  children: string;
  tone?: "neutral" | "blue" | "green" | "yellow" | "orange" | "red";
  className?: string;
}

const toneClasses = {
  neutral: "text-app-muted",
  blue: "text-[#75beff]",
  green: "text-app-good",
  yellow: "text-app-warning",
  orange: "text-app-mistake",
  red: "text-app-blunder",
};

const classificationSymbols: Record<MoveClassification, string> = {
  Excellent: "!",
  Inaccuracy: "?!",
  Mistake: "?",
  Blunder: "??",
};

export function Badge({ children, tone = "neutral", className = "" }: BadgeProps) {
  return (
    <span className={`inline-flex items-center text-xs font-medium ${toneClasses[tone]} ${className}`}>
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
