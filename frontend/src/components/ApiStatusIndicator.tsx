interface ApiStatusIndicatorProps {
  status: "checking" | "ok" | "down";
}

const config: Record<ApiStatusIndicatorProps["status"], { color: string; label: string }> = {
  checking: { color: "#9aa0aa", label: "Connecting" },
  ok: { color: "#34d399", label: "Connected" },
  down: { color: "#f43f5e", label: "Offline" },
};

export function ApiStatusIndicator({ status }: ApiStatusIndicatorProps) {
  const { color, label } = config[status];

  return (
    <div className="inline-flex items-center gap-2 text-xs font-medium text-app-muted" title={`API ${status}`}>
      <span className="relative flex h-2 w-2" aria-label={`API ${status}`}>
        {status === "checking" && (
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60"
            style={{ backgroundColor: color }}
          />
        )}
        <span className="relative inline-flex h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
      </span>
      <span className="uppercase tracking-[0.14em]">{label}</span>
    </div>
  );
}
