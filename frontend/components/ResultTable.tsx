import { fmtChange, fmtInt, fmtMs, fmtSize } from "@/lib/format";
import type { TestResult } from "@/lib/types";
import { cx } from "./ui";

function Change({ value, good }: { value: string; good: boolean | null }) {
  return (
    <span className={cx("font-medium", good === null ? "text-slate-500" : good ? "text-emerald-700" : "text-amber-700")}>
      {value}
    </span>
  );
}

export default function ResultTable({ result }: { result: TestResult }) {
  const r = result;
  const rows = [
    {
      measure: "Query time (median)",
      before: fmtMs(r.before_ms),
      after: fmtMs(r.after_ms),
      change: <Change value={fmtChange(r.before_ms, r.after_ms)} good={r.after_ms <= r.before_ms} />,
    },
    {
      measure: "Rows examined (plan estimate)",
      before: fmtInt(r.rows_before),
      after: fmtInt(r.rows_after),
      change: <Change value={fmtChange(r.rows_before, r.rows_after)} good={r.rows_after <= r.rows_before} />,
    },
    {
      measure: "Access plan",
      before: r.plan_before,
      after: r.plan_after,
      change: <Change value={r.plan_before === r.plan_after ? "unchanged" : "changed"} good={r.plan_before === r.plan_after ? null : true} />,
    },
    {
      measure: `INSERT ${fmtInt(r.insert_rows)} rows`,
      before: fmtMs(r.insert_before_ms),
      after: fmtMs(r.insert_after_ms),
      change: (
        <Change
          value={`${r.write_loss_pct > 0 ? "+" : ""}${r.write_loss_pct}% ${r.write_loss_pct > 0 ? "slower" : "faster"}`}
          good={r.write_loss_pct <= 0}
        />
      ),
    },
    {
      measure: "Index size",
      before: "–",
      after: fmtSize(r.index_size_kb),
      change: <Change value="extra disk" good={null} />,
    },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
            <th className="py-2 pr-4 font-medium">Measure</th>
            <th className="py-2 pr-4 text-right font-medium">Before</th>
            <th className="py-2 pr-4 text-right font-medium">After</th>
            <th className="py-2 text-right font-medium">Change</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.measure}>
              <td className="py-2.5 pr-4 text-slate-600">{row.measure}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-slate-900">{row.before}</td>
              <td className="py-2.5 pr-4 text-right font-semibold tabular-nums text-slate-900">{row.after}</td>
              <td className="py-2.5 text-right tabular-nums">{row.change}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-xs text-slate-500">
        Runs before: {r.before_timings.map((t) => fmtMs(t)).join(" · ")} — after:{" "}
        {r.after_timings.map((t) => fmtMs(t)).join(" · ")}
      </p>
    </div>
  );
}
