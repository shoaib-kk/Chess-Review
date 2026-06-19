import type { MoveClassification } from "../../types";
import { classificationMeta, type BadgeTone } from "../../utils/classification";

interface BadgeProps {
  children: string;
  tone?: BadgeTone;
  className?: string;
}

const toneClasses: Record<BadgeTone, string> = {
  neutral: "bg-app-panelSecondary text-app-muted ring-app-border",
  blue: "bg-[#2cc7b815] text-[#5fd6c9] ring-[#2cc7b833]",
  green: "bg-[#56b27715] text-app-good ring-[#56b27733]",
  yellow: "bg-[#d6b24a15] text-app-warning ring-[#d6b24a33]",
  orange: "bg-[#d9863e15] text-app-mistake ring-[#d9863e33]",
  red: "bg-[#d9574f15] text-app-blunder ring-[#d9574f33]",
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
  const meta = classificationMeta(classification);
  const text = meta.badgeSymbol ? `${meta.label} ${meta.badgeSymbol}` : meta.label;
  return <Badge tone={meta.tone}>{text}</Badge>;
}
