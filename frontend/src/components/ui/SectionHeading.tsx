import type { ReactNode } from "react";

interface SectionHeadingProps {
  title: string;
  /** Small uppercase eyebrow above the title. */
  eyebrow?: string;
  /** Right-aligned action (link/button). */
  action?: ReactNode;
  className?: string;
}

/** A consistent section title row used to separate dashboard regions. */
export function SectionHeading({ title, eyebrow, action, className = "" }: SectionHeadingProps) {
  return (
    <div className={`mb-3 flex items-end justify-between gap-4 ${className}`}>
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-app-accent/80">{eyebrow}</p>
        )}
        <h2 className="text-[15px] font-semibold tracking-tight text-app-text">{title}</h2>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
