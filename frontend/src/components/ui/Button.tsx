import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "control";
type ButtonSize = "sm" | "md" | "lg" | "icon";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-app-accent text-app-accentFg font-semibold shadow-[0_1px_0_0_rgba(255,255,255,0.15)_inset,0_6px_16px_-8px_rgba(200,161,90,0.6)] hover:bg-app-accentHover active:translate-y-px disabled:bg-app-raised disabled:text-app-faint disabled:shadow-none",
  secondary:
    "bg-app-raised text-app-text ring-1 ring-inset ring-app-border bg-surface-sheen hover:bg-app-raisedHover hover:ring-app-borderStrong active:translate-y-px disabled:text-app-faint",
  ghost:
    "bg-transparent text-app-muted hover:bg-app-raised hover:text-app-text disabled:text-app-faint",
  control:
    "bg-app-raised text-app-text ring-1 ring-inset ring-app-border hover:bg-app-raisedHover disabled:text-app-faint",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-9 gap-1.5 px-3 text-sm rounded-lg",
  md: "h-10 gap-2 px-4 text-sm rounded-lg",
  lg: "h-12 gap-2 px-5 text-[15px] rounded-xl",
  icon: "h-10 w-10 text-sm rounded-lg",
};

export function Button({
  variant = "secondary",
  size = "md",
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center font-medium transition duration-150 ease-spring focus:outline-none focus-visible:ring-2 focus-visible:ring-app-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-app-bg disabled:cursor-not-allowed ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
