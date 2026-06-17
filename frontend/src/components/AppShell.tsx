import type { ReactNode } from "react";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="relative min-h-screen text-app-text">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10"
        style={{
          background: "linear-gradient(180deg, #101116 0%, #0e0f13 42%, #0e0f13 100%)",
        }}
      />
      {children}
    </div>
  );
}
