import type { MoveClassification } from "../../types";

interface BadgeProps {
  children: string;
  tone?: "neutral" | "blue" | "green" | "yellow" | "orange" | "red";
  className?: string;
}

const toneClasses = {
  neutral: "bg-app-panelSecondary text-app-muted",
  blue: "bg-blue-500/15 text-blue-300",
  green: "bg-app-good/15 text-green-300",
  yellow: "bg-app-warning/15 text-yellow-300",
  orange: "bg-app-mistake/15 text-orange-300",
  red: "bg-app-blunder/15 text-red-300",
};

export function Badge({ children, tone = "neutral", className = "" }: BadgeProps) {
  return (
    <span className={`inline-flex items-center rounded px-2 py-1 text-xs font-bold ${toneClasses[tone]} ${className}`}>
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

  return <Badge tone={tone}>{classification}</Badge>;
}
