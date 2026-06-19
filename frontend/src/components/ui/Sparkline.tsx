interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  /** Stroke colour; defaults to the warm accent. */
  color?: string;
  /** Soft area fill under the line. */
  fill?: boolean;
  className?: string;
  strokeWidth?: number;
}

/**
 * A tiny, dependency-free SVG sparkline. Renders a smooth-ish polyline with an
 * optional gradient area fill and a dot on the latest point.
 */
export function Sparkline({
  data,
  width = 120,
  height = 36,
  color = "#c8a15a",
  fill = true,
  className = "",
  strokeWidth = 1.75,
}: SparklineProps) {
  const points = data.filter((n) => Number.isFinite(n));
  if (points.length < 2) {
    return (
      <svg width={width} height={height} className={className} aria-hidden>
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke={color}
          strokeWidth={strokeWidth}
          strokeOpacity={0.4}
          strokeDasharray="3 3"
        />
      </svg>
    );
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const pad = strokeWidth + 1;
  const innerH = height - pad * 2;
  const stepX = width / (points.length - 1);

  const coords = points.map((value, i) => {
    const x = i * stepX;
    const y = pad + innerH - ((value - min) / range) * innerH;
    return [x, y] as const;
  });

  const linePath = coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  const areaPath = `${linePath} L${width},${height} L0,${height} Z`;
  const gradId = `spark-${Math.round(width)}-${color.replace(/[^a-z0-9]/gi, "")}`;
  const [lastX, lastY] = coords[coords.length - 1];

  return (
    <svg width={width} height={height} className={className} aria-hidden viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.22} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      {fill && <path d={areaPath} fill={`url(#${gradId})`} />}
      <path d={linePath} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={lastX} cy={lastY} r={2.4} fill={color} />
      <circle cx={lastX} cy={lastY} r={4.5} fill={color} fillOpacity={0.18} />
    </svg>
  );
}
