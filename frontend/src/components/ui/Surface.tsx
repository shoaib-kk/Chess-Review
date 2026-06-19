import type { ElementType, ReactNode } from "react";

type SurfaceVariant = "surface" | "raised" | "glass";

interface SurfaceProps {
  children: ReactNode;
  /** Visual elevation. */
  variant?: SurfaceVariant;
  /** Adds hover lift + brighter border. Use for clickable cards. */
  interactive?: boolean;
  /** Render as a different element (e.g. "button", "a"). */
  as?: ElementType;
  className?: string;
  [key: string]: unknown;
}

const variantClass: Record<SurfaceVariant, string> = {
  surface: "surface",
  raised: "surface-raised",
  glass: "glass rounded-2xl shadow-raised",
};

/**
 * The base card surface for the redesigned UI: a layered fill with a faint
 * top sheen and soft elevation. Depth comes from the surface, not heavy borders.
 */
export function Surface({
  children,
  variant = "surface",
  interactive = false,
  as,
  className = "",
  ...rest
}: SurfaceProps) {
  const Component = (as ?? "div") as ElementType;
  return (
    <Component
      className={`${variantClass[variant]} ${interactive ? "card-interactive focus-ring text-left" : ""} ${className}`}
      {...rest}
    >
      {children}
    </Component>
  );
}
