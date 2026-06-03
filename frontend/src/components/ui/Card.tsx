import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
}

interface CardHeaderProps {
  title: string;
  eyebrow?: string;
  action?: ReactNode;
  children?: ReactNode;
}

export function Card({ children, className = "" }: CardProps) {
  return (
    <section className={`bg-app-panel ${className}`}>
      {children}
    </section>
  );
}

export function CardHeader({ title, eyebrow, action, children }: CardHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 px-5 pb-3 pt-5">
      <div className="min-w-0">
        {eyebrow && <p className="mb-1 text-[11px] font-medium uppercase tracking-[0.18em] text-app-muted">{eyebrow}</p>}
        <h2 className="truncate text-base font-medium text-app-text">{title}</h2>
        {children && <div className="mt-1 text-sm text-app-muted">{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
