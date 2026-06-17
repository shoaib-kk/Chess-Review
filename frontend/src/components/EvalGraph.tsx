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
  Excellent: "#34d399",
  Inaccuracy: "#fbbf24",
  Mistake: "#fb923c",
  Blunder: "#f43f5e",
};

function clampEval(value: number | null): number {
  if (value === null) return 0;
  return Math.max(-10, Math.min(10, value));
}

function evalText(value: number | null) {
  if (value === null || Math.abs(value) < 0.3) return "Equal";
  if (value > 0) return value > 3 ? "White is winning" : "White is better";
  return value < -3 ? "Black is winning" : "Black is better";
}

export function EvalGraphPanel({ summary, currentIndex, onSelectMove, embedded = false }: EvalGraphPanelProps) {
  const data = summary.move_analyses.map((move, index) => ({
    index,
    label: `${move.move_number}${move.color === "White" ? "." : "..."} ${move.move_played}`,
    eval: clampEval(move.eval_white_pov),
    classification: move.classification,
  }));

  const content = (
    <>
      <div className="px-5 pb-2 pt-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-app-accent/80">Position trend</p>
        <h2 className="mt-1 text-base font-semibold text-app-text">Evaluation</h2>
        <p className="mt-1 text-xs text-app-muted">Above zero favors White; below zero favors Black.</p>
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
            <CartesianGrid stroke="#262a33" strokeDasharray="3 6" vertical={false} />
            <XAxis dataKey="index" tick={{ fill: "#8b93a1", fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis
              domain={[-10, 10]}
              ticks={[-5, 0, 5]}
              tick={{ fill: "#8b93a1", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ stroke: "#6366f1", strokeWidth: 1, strokeDasharray: "4 4" }}
              contentStyle={{ background: "#16181d", border: "1px solid #262a33", borderRadius: 12 }}
              labelStyle={{ color: "#e7e9ee" }}
              formatter={(value, _name, props) => [evalText(Number(value)), props.payload.label]}
            />
            <ReferenceLine y={0} stroke="#8b93a155" />
            {currentIndex >= 0 && <ReferenceLine x={currentIndex} stroke="#6366f1" strokeDasharray="4 4" />}
            <Line
              type="monotone"
              dataKey="eval"
              stroke="#6366f1"
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
                    fill={important ? COLORS[payload.classification] : "#5b6270"}
                    stroke="#0e0f13"
                    strokeWidth={1}
                  />
                );
              }}
              activeDot={{ r: 7, fill: "#6366f1", stroke: "#0e0f13", strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </>
  );

  if (embedded) return <section>{content}</section>;

  return (
    <Card className="overflow-hidden">
      {content}
    </Card>
  );
}
