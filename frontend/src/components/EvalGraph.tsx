import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { GameSummary, MoveClassification } from "../types";
import { classificationMeta } from "../utils/classification";
import { cpToWinChance, formatEval, isMateScore } from "../utils/evalFormat";
import { Card } from "./ui/Card";

interface EvalGraphPanelProps {
  summary: GameSummary;
  currentIndex: number;
  onSelectMove: (index: number) => void;
  embedded?: boolean;
}

/** White's win chance (0-100) for an eval given in pawns from White's POV. */
function whiteWinChance(evalPawns: number | null): number {
  if (evalPawns === null) return 50;
  return cpToWinChance(evalPawns * 100);
}

function evalText(evalPawns: number | null) {
  if (evalPawns === null) return "Equal";
  const cp = evalPawns * 100;
  if (isMateScore(cp)) return cp > 0 ? "White has forced mate" : "Black has forced mate";
  if (Math.abs(evalPawns) < 0.3) return "Equal";
  if (evalPawns > 0) return evalPawns > 3 ? "White is winning" : "White is better";
  return evalPawns < -3 ? "Black is winning" : "Black is better";
}

export function EvalGraphPanel({ summary, currentIndex, onSelectMove, embedded = false }: EvalGraphPanelProps) {
  const data = summary.move_analyses.map((move, index) => ({
    index,
    label: `${move.move_number}${move.color === "White" ? "." : "..."} ${move.move_played}`,
    // Win probability is bounded yet keeps decisive positions distinct from one
    // another near the edges — far more legible than a hard ±10 clamp on raw eval.
    winProb: whiteWinChance(move.eval_white_pov),
    evalPawns: move.eval_white_pov,
    classification: move.classification,
  }));

  const content = (
    <>
      <div className="pb-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-app-faint">Position trend</p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight text-app-text">Win probability</h2>
        <p className="mt-1 text-xs text-app-muted">The filled area is White's winning chances; the rest is Black's.</p>
      </div>
      <div className="-ml-2 h-48">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 10, right: 12, left: -20, bottom: 0 }}
            onClick={(event) => {
              const index = event?.activePayload?.[0]?.payload?.index;
              if (typeof index === "number") onSelectMove(index);
            }}
          >
            <defs>
              <linearGradient id="winProbFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f0f1f4" stopOpacity={0.95} />
                <stop offset="55%" stopColor="#cfd3da" stopOpacity={0.85} />
                <stop offset="100%" stopColor="#9aa0ab" stopOpacity={0.7} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#222328" strokeDasharray="3 6" vertical={false} />
            <XAxis dataKey="index" tick={{ fill: "#85868f", fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 50, 100]}
              tickFormatter={(value) => `${value}%`}
              tick={{ fill: "#85868f", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ stroke: "#c8a15a", strokeWidth: 1, strokeDasharray: "4 4" }}
              contentStyle={{ background: "#191a1e", border: "1px solid #34363d", borderRadius: 10, boxShadow: "0 16px 48px -16px rgba(0,0,0,0.7)" }}
              labelStyle={{ color: "#f3f3f5" }}
              formatter={(_value, _name, props) => {
                const p = props.payload as { evalPawns: number | null; label: string; winProb: number };
                return [`${formatEval(p.evalPawns === null ? null : p.evalPawns * 100)} · ${evalText(p.evalPawns)}`, p.label];
              }}
            />
            <ReferenceLine y={50} stroke="#85868f55" />
            {currentIndex >= 0 && <ReferenceLine x={currentIndex} stroke="#c8a15a" strokeDasharray="4 4" />}
            <Area
              type="monotone"
              dataKey="winProb"
              stroke="#e7e8ec"
              strokeWidth={1.5}
              fill="url(#winProbFill)"
              isAnimationActive={false}
              activeDot={{ r: 6, fill: "#c8a15a", stroke: "#0a0a0c", strokeWidth: 2 }}
              dot={(props) => {
                const payload = props.payload as { classification: MoveClassification; index: number };
                const meta = classificationMeta(payload.classification);
                const important = meta.isError || meta.isHighlight;
                if (!important) {
                  return <circle key={payload.index} cx={props.cx} cy={props.cy} r={0} fill="none" />;
                }
                return (
                  <circle
                    key={payload.index}
                    cx={props.cx}
                    cy={props.cy}
                    r={5}
                    fill={meta.color}
                    stroke="#0a0a0c"
                    strokeWidth={1.5}
                  />
                );
              }}
            />
          </AreaChart>
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
