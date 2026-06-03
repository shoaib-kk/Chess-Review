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
import { Card } from "./ui/Card";

interface EvalGraphPanelProps {
  summary: GameSummary;
  currentIndex: number;
  onSelectMove: (index: number) => void;
  embedded?: boolean;
}

const COLORS: Record<MoveClassification, string> = {
  Excellent: "#22c55e",
  Inaccuracy: "#eab308",
  Mistake: "#f97316",
  Blunder: "#ef4444",
};

function clampEval(value: number | null): number {
  if (value === null) return 0;
  return Math.max(-10, Math.min(10, value));
}

export function EvalGraphPanel({ summary, currentIndex, onSelectMove, embedded = false }: EvalGraphPanelProps) {
  const data = summary.move_analyses.map((move, index) => ({
    index,
    label: `${move.move_number}${move.color === "White" ? "." : "..."} ${move.move_played}`,
    eval: clampEval(move.eval_white_pov),
    classification: move.classification,
    cpLoss: move.cp_loss,
  }));

  const content = (
    <>
      <div className="px-5 pb-2 pt-4">
        <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-app-muted">Engine line</p>
        <h2 className="mt-1 text-base font-medium text-app-text">Evaluation</h2>
      </div>
      <div className="h-48 px-3 pb-4">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 10, right: 12, left: -20, bottom: 0 }}
            onClick={(event) => {
              const index = event?.activePayload?.[0]?.payload?.index;
              if (typeof index === "number") onSelectMove(index);
            }}
          >
            <CartesianGrid stroke="#263244" strokeDasharray="3 6" vertical={false} />
            <XAxis dataKey="index" tick={{ fill: "#94a3b8", fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis
              domain={[-10, 10]}
              ticks={[-5, 0, 5]}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ stroke: "#3b82f6", strokeWidth: 1, strokeDasharray: "4 4" }}
              contentStyle={{ background: "#111827", border: "1px solid #263244", borderRadius: 6 }}
              labelStyle={{ color: "#f8fafc" }}
              formatter={(value, _name, props) => [`${Number(value).toFixed(2)}`, props.payload.label]}
            />
            <ReferenceLine y={0} stroke="#94a3b855" />
            {currentIndex >= 0 && <ReferenceLine x={currentIndex} stroke="#3b82f6" strokeDasharray="4 4" />}
            <Line
              type="monotone"
              dataKey="eval"
              stroke="#cbd5e1"
              strokeWidth={2}
              dot={(props) => {
                const payload = props.payload as { classification: MoveClassification; index: number };
                const important = payload.classification !== "Excellent";
                return (
                  <circle
                    key={payload.index}
                    cx={props.cx}
                    cy={props.cy}
                    r={important ? 5 : 2.5}
                    fill={important ? COLORS[payload.classification] : "#64748b"}
                    stroke="#0b1120"
                    strokeWidth={1}
                  />
                );
              }}
              activeDot={{ r: 7, fill: "#3b82f6", stroke: "#0b1120", strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </>
  );

  if (embedded) return <section>{content}</section>;

  return (
    <Card className="overflow-hidden ring-1 ring-app-border/70">
      {content}
    </Card>
  );
}
