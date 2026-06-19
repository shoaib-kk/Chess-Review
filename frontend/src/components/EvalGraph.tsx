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
import { classificationMeta } from "../utils/classification";
import { Card } from "./ui/Card";

interface EvalGraphPanelProps {
  summary: GameSummary;
  currentIndex: number;
  onSelectMove: (index: number) => void;
  embedded?: boolean;
}

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
      <div className="pb-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">Position trend</p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-app-text">Evaluation</h2>
        <p className="mt-1 text-xs text-app-muted">Above zero favors White; below zero favors Black.</p>
      </div>
      <div className="-ml-2 h-48">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 10, right: 12, left: -20, bottom: 0 }}
            onClick={(event) => {
              const index = event?.activePayload?.[0]?.payload?.index;
              if (typeof index === "number") onSelectMove(index);
            }}
          >
            <CartesianGrid stroke="#222328" strokeDasharray="3 6" vertical={false} />
            <XAxis dataKey="index" tick={{ fill: "#85868f", fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis
              domain={[-10, 10]}
              ticks={[-5, 0, 5]}
              tick={{ fill: "#85868f", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ stroke: "#c8a15a", strokeWidth: 1, strokeDasharray: "4 4" }}
              contentStyle={{ background: "#191a1e", border: "1px solid #34363d", borderRadius: 10, boxShadow: "0 16px 48px -16px rgba(0,0,0,0.7)" }}
              labelStyle={{ color: "#f3f3f5" }}
              formatter={(value, _name, props) => [evalText(Number(value)), props.payload.label]}
            />
            <ReferenceLine y={0} stroke="#85868f55" />
            {currentIndex >= 0 && <ReferenceLine x={currentIndex} stroke="#c8a15a" strokeDasharray="4 4" />}
            <Line
              type="monotone"
              dataKey="eval"
              stroke="#c8a15a"
              strokeWidth={2}
              dot={(props) => {
                const payload = props.payload as { classification: MoveClassification; index: number };
                const meta = classificationMeta(payload.classification);
                const important = meta.isError || meta.isHighlight;
                return (
                  <circle
                    key={payload.index}
                    cx={props.cx}
                    cy={props.cy}
                    r={important ? 5 : 2.5}
                    fill={important ? meta.color : "#5b6270"}
                    stroke="#0a0a0c"
                    strokeWidth={1}
                  />
                );
              }}
              activeDot={{ r: 7, fill: "#c8a15a", stroke: "#0a0a0c", strokeWidth: 2 }}
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
