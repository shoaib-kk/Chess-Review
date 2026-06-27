// Recharts visualisations for the profile dashboard (Section 8).
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  Treemap,
  XAxis,
  YAxis,
} from "recharts";
import type { ProfileFeatures } from "./types";

const ACCENT = "#5eead4"; // app-accent-ish teal
const GRID = "rgba(255,255,255,0.08)";
const AXIS = "rgba(255,255,255,0.45)";

const clamp01 = (n: number | null | undefined) =>
  n == null ? 0 : Math.max(0, Math.min(1, n));

// Six style axes, each normalised to 0-1 so they share one radar scale.
export function styleRadarData(f: ProfileFeatures) {
  return [
    { axis: "Aggression", value: clamp01(f.style.aggression_index) },
    { axis: "Tactics", value: clamp01(f.tactical.tactical_opportunity_conversion) },
    { axis: "Sacrifice", value: clamp01(f.tactical.sacrifice_tendency) },
    { axis: "Initiative", value: clamp01(f.style.initiative_index) },
    { axis: "Accuracy", value: clamp01((f.accuracy.accuracy_score ?? 0) / 100) },
    { axis: "Endgame", value: clamp01((f.endgame.endgame_accuracy ?? 0) / 100) },
  ];
}

export function StyleRadar({ features }: { features: ProfileFeatures }) {
  const data = styleRadarData(features);
  return (
    <ResponsiveContainer width="100%" height={260}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke={GRID} />
        <PolarAngleAxis dataKey="axis" tick={{ fill: AXIS, fontSize: 11 }} />
        <Radar dataKey="value" stroke={ACCENT} fill={ACCENT} fillOpacity={0.35} />
        <Tooltip
          contentStyle={{ background: "#0f1729", border: "1px solid " + GRID, borderRadius: 8 }}
          formatter={(v: number) => [(v * 100).toFixed(0) + "%", "score"]}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}

// Accuracy (0-100) across the three game phases that the profile exposes.
export function AccuracyByPhase({ features }: { features: ProfileFeatures }) {
  const data = [
    { phase: "Opening", accuracy: features.opening.opening_accuracy ?? 0 },
    { phase: "Overall", accuracy: features.accuracy.accuracy_score ?? 0 },
    { phase: "Endgame", accuracy: features.endgame.endgame_accuracy ?? 0 },
  ];
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="phase" tick={{ fill: AXIS, fontSize: 12 }} axisLine={false} tickLine={false} />
        <YAxis domain={[0, 100]} tick={{ fill: AXIS, fontSize: 11 }} axisLine={false} tickLine={false} />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
          contentStyle={{ background: "#0f1729", border: "1px solid " + GRID, borderRadius: 8 }}
          formatter={(v: number) => [Number(v).toFixed(1), "accuracy"]}
        />
        <Bar dataKey="accuracy" radius={[6, 6, 0, 0]} fill={ACCENT} />
      </BarChart>
    </ResponsiveContainer>
  );
}

const TREEMAP_COLORS = ["#0d9488", "#0e7490", "#1d4ed8", "#6d28d9", "#9333ea", "#be185d", "#b45309"];

export function OpeningTreemap({ ecoDistribution }: { ecoDistribution: Record<string, number> }) {
  const entries = Object.entries(ecoDistribution || {});
  if (entries.length === 0) {
    return <p className="py-10 text-center text-sm text-app-subtle">No opening data yet.</p>;
  }
  const data = entries
    .sort((a, b) => b[1] - a[1])
    .map(([eco, count], i) => ({ name: eco, size: count, fill: TREEMAP_COLORS[i % TREEMAP_COLORS.length] }));
  return (
    <ResponsiveContainer width="100%" height={260}>
      <Treemap data={data} dataKey="size" nameKey="name" stroke="#0b1120" content={<TreemapCell />}>
        <Tooltip
          contentStyle={{ background: "#0f1729", border: "1px solid " + GRID, borderRadius: 8 }}
          formatter={(v: number, _n, p: { payload?: { name?: string } }) => [`${v} games`, p?.payload?.name ?? ""]}
        />
      </Treemap>
    </ResponsiveContainer>
  );
}

function TreemapCell(props: any) {
  const { x, y, width, height, name, fill } = props;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={fill} stroke="#0b1120" />
      {width > 40 && height > 22 && (
        <text x={x + 6} y={y + 18} fill="#e2e8f0" fontSize={12} fontWeight={600}>
          {name}
        </text>
      )}
    </g>
  );
}

export function TradePreferenceBars({ prefs }: { prefs: Record<string, number> | null }) {
  const entries = Object.entries(prefs || {});
  if (!entries.length) return null;
  const labels: Record<string, string> = { Q: "Queen", R: "Rook", B: "Bishop", N: "Knight", P: "Pawn" };
  const data = entries.map(([piece, v]) => ({ piece: labels[piece] ?? piece, value: Math.round(v * 100) }));
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
        <CartesianGrid stroke={GRID} horizontal={false} />
        <XAxis type="number" domain={[0, 100]} hide />
        <YAxis type="category" dataKey="piece" tick={{ fill: AXIS, fontSize: 12 }} axisLine={false} tickLine={false} width={56} />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
          contentStyle={{ background: "#0f1729", border: "1px solid " + GRID, borderRadius: 8 }}
          formatter={(v: number) => [v + "%", "trade tendency"]}
        />
        <Bar dataKey="value" radius={[0, 6, 6, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.value >= 50 ? ACCENT : "#64748b"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
