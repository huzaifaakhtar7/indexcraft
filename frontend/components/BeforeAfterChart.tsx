"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtMs } from "@/lib/format";
import type { TestResult } from "@/lib/types";
import { cx } from "./ui";

const MIN = 0.01;

function TimeChart({ title, note, before, after, afterColor, log }: {
  title: string;
  note: string;
  before: number;
  after: number;
  afterColor: string;
  log: boolean;
}) {
  const data = [
    { name: "Before", value: Math.max(before, MIN), raw: before, color: "#94a3b8" },
    { name: "After", value: Math.max(after, MIN), raw: after, color: afterColor },
  ];
  const low = Math.max(Math.min(before, after), MIN);

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      <p className="text-xs text-slate-500">{note}</p>
      <div className="mt-3 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 24, right: 8, bottom: 0, left: 8 }}>
            <CartesianGrid vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fill: "#475569", fontSize: 12 }} />
            <YAxis
              scale={log ? "log" : "linear"}
              domain={log ? [low / 2, "auto"] : [0, "auto"]}
              allowDataOverflow={log}
              tickFormatter={(v) => fmtMs(Number(v))}
              tickLine={false}
              axisLine={false}
              width={64}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
            />
            <Tooltip
              cursor={{ fill: "#f1f5f9" }}
              formatter={(_, __, item) => [fmtMs((item.payload as { raw: number }).raw), "Median time"]}
            />
            <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={72} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.name} fill={d.color} />
              ))}
              <LabelList
                dataKey="raw"
                position="top"
                formatter={(v) => fmtMs(Number(v))}
                style={{ fill: "#0f172a", fontSize: 12, fontWeight: 600 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function BeforeAfterChart({ result }: { result: TestResult }) {
  const [log, setLog] = useState(false);

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs font-medium">
          {[false, true].map((value) => (
            <button
              key={String(value)}
              type="button"
              onClick={() => setLog(value)}
              className={cx("rounded-md px-3 py-1", log === value ? "bg-white text-slate-900 shadow-sm" : "text-slate-500")}
            >
              {value ? "Log scale" : "Linear"}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-2 [&>*]:min-w-0">
        <TimeChart
          title="Query time"
          note="median of runs, lower is better"
          before={result.before_ms}
          after={result.after_ms}
          afterColor="#4f46e5"
          log={log}
        />
        <TimeChart
          title={`INSERT ${result.insert_rows.toLocaleString("en-US")} rows`}
          note="cost of the index on writes"
          before={result.insert_before_ms}
          after={result.insert_after_ms}
          afterColor="#f59e0b"
          log={log}
        />
      </div>
    </div>
  );
}
