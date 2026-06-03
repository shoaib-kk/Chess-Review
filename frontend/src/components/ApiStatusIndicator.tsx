interface ApiStatusIndicatorProps {
  status: "checking" | "ok" | "down";
}

const dotColor: Record<ApiStatusIndicatorProps["status"], string> = {
  checking: "#94a3b8",
  ok: "#22c55e",
  down: "#ef4444",
};

export function ApiStatusIndicator({ status }: ApiStatusIndicatorProps) {
  return (
    <div className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-app-muted" title={`API ${status}`}>
      <span>API</span>
      <span className="inline-flex items-center gap-1" aria-label={`API ${status}`}>
        {[0, 1, 2].map((index) => (
          <span key={index} className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: dotColor[status] }} />
        ))}
      </span>
    </div>
  );
}
