import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "control";
type ButtonSize = "sm" | "md" | "icon";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-app-accent text-white shadow-sm hover:bg-app-accentHover active:translate-y-px disabled:bg-app-panelSecondary disabled:text-app-faint disabled:shadow-none",
  secondary:
    "bg-app-panelSecondary text-app-text ring-1 ring-inset ring-app-border hover:bg-app-panelHover hover:ring-app-borderStrong disabled:text-app-faint",
  ghost:
    "bg-transparent text-app-muted hover:bg-app-panelSecondary hover:text-app-text disabled:text-app-faint",
  control:
    "bg-app-panelSecondary/60 text-app-text ring-1 ring-inset ring-app-border hover:bg-app-panelHover disabled:text-app-faint",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-9 gap-1.5 px-3 text-sm",
  md: "h-11 gap-2 px-4 text-sm",
  icon: "h-10 w-10 text-sm",
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
      className={`inline-flex items-center justify-center rounded-lg font-medium transition duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-app-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-app-bg disabled:cursor-not-allowed ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
