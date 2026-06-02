import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { GameSummary, MoveClassification } from "../types";

interface EvalGraphProps {
  summary: GameSummary;
  currentIndex: number;
  onSelectMove: (index: number) => void;
}

const COLORS: Record<MoveClassification, string> = {
  Excellent: "#4ade80",
  Inaccuracy: "#facc15",
  Mistake: "#f97316",
  Blunder: "#ef4444",
};

function clampEval(value: number | null): number {
  if (value === null) return 0;
  return Math.max(-10, Math.min(10, value));
}

export function EvalGraph({ summary, currentIndex, onSelectMove }: EvalGraphProps) {
  const data = summary.move_analyses.map((move, index) => ({
    index,
    label: `${move.move_number}${move.color === "White" ? "." : "..."} ${move.move_played}`,
    eval: clampEval(move.eval_white_pov),
    rawEval: move.eval_white_pov,
    classification: move.classification,
    cpLoss: move.cp_loss,
  }));

  return (
    <section className="rounded bg-app-panel p-4 shadow-panel">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Evaluation</p>
        <p className="text-xs text-slate-400">White advantage above zero</p>
      </div>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} onClick={(event) => {
            const index = event?.activePayload?.[0]?.payload?.index;
            if (typeof index === "number") onSelectMove(index);
          }}>
            <CartesianGrid stroke="#ffffff12" vertical={false} />
            <XAxis dataKey="index" tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#334155" }} />
            <YAxis domain={[-10, 10]} ticks={[-5, 0, 5]} tick={{ fill: "#64748b", fontSize: 11 }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 6 }}
              labelStyle={{ color: "#e2e8f0" }}
              formatter={(value, _name, props) => [
                `${Number(value).toFixed(2)}`,
                props.payload.label,
              ]}
            />
            <ReferenceLine y={0} stroke="#ffffff40" />
            {currentIndex >= 0 && <ReferenceLine x={currentIndex} stroke="#3b82f6" strokeDasharray="4 4" />}
            <Line
              type="monotone"
              dataKey="eval"
              stroke="#94a3b8"
              strokeWidth={2}
              dot={(props) => {
                const payload = props.payload as { classification: MoveClassification; index: number };
                const radius = payload.classification === "Excellent" ? 3 : 5;
                return (
                  <circle
                    key={payload.index}
                    cx={props.cx}
                    cy={props.cy}
                    r={radius}
                    fill={COLORS[payload.classification]}
                    stroke="#0f172a"
                    strokeWidth={1}
                  />
                );
              }}
              activeDot={{ r: 7, fill: "#3b82f6" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
