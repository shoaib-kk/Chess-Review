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
    "bg-app-accent text-white shadow-glow hover:bg-blue-500 disabled:bg-app-panelSecondary disabled:text-app-muted disabled:shadow-none",
  secondary:
    "bg-app-panelSecondary text-app-text hover:bg-slate-700 disabled:text-app-muted disabled:bg-app-panelSecondary/60",
  ghost:
    "bg-transparent text-app-muted hover:bg-app-panelSecondary/80 hover:text-app-text disabled:text-slate-600",
  control:
    "bg-slate-950/70 text-app-text hover:bg-app-panelSecondary disabled:text-slate-600",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-sm",
  md: "h-11 px-4 text-sm",
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
      className={`inline-flex items-center justify-center rounded-md font-semibold transition duration-150 focus:outline-none focus:ring-2 focus:ring-app-accent/50 disabled:cursor-not-allowed ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
