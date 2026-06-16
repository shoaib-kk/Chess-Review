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
          background:
            "radial-gradient(1100px 600px at 85% -8%, rgba(99,102,241,0.10), transparent 60%)," +
            "radial-gradient(900px 500px at -10% 110%, rgba(99,102,241,0.06), transparent 55%)," +
            "#0e0f13",
        }}
      />
      {children}
    </div>
  );
}
