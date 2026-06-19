import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  /** Strip the surface chrome (border/fill/shadow) — for nesting inside a Card. */
  flush?: boolean;
  /** Remove default padding (caller controls spacing). */
  bare?: boolean;
}

interface CardHeaderProps {
  title: string;
  eyebrow?: string;
  action?: ReactNode;
  children?: ReactNode;
}

/**
 * A layered surface card. Depth comes from the surface fill + sheen + soft
 * shadow rather than heavy borders. Use `flush` for sub-sections nested inside
 * another Card so they don't stack a second surface.
 */
export function Card({ children, className = "", flush = false, bare = false }: CardProps) {
  const chrome = flush ? "" : "surface";
  const pad = bare ? "" : "p-5 sm:p-6";
  return <section className={`${chrome} ${pad} ${className}`}>{children}</section>;
}

export function CardHeader({ title, eyebrow, action, children }: CardHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 pb-4">
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-app-accent/80">{eyebrow}</p>
        )}
        <h2 className="truncate text-lg font-semibold tracking-tight text-app-text">{title}</h2>
        {children && <div className="mt-1.5 text-sm text-app-muted">{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
