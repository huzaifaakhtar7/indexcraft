"use client";

import { useRouter } from "next/navigation";
import { DB_LABELS, fmtDate, fmtMs, fmtSpeedup, VERDICT_STYLE } from "@/lib/format";
import type { HistoryRun } from "@/lib/types";
import { Badge } from "./ui";

export default function HistoryTable({ runs }: { runs: HistoryRun[] }) {
  const router = useRouter();

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[48rem] text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
            <th className="py-2 pr-4 font-medium">#</th>
            <th className="py-2 pr-4 font-medium">Date</th>
            <th className="py-2 pr-4 font-medium">Database</th>
            <th className="py-2 pr-4 font-medium">Query</th>
            <th className="py-2 pr-4 text-right font-medium">Baseline</th>
            <th className="py-2 pr-4 text-right font-medium">Best speed-up</th>
            <th className="py-2 font-medium">Best verdict</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {runs.map((r) => (
            <tr
              key={r.run_id}
              tabIndex={0}
              onClick={() => router.push(`/history/${r.run_id}`)}
              onKeyDown={(e) => {
                if (e.key === "Enter") router.push(`/history/${r.run_id}`);
              }}
              className="cursor-pointer transition hover:bg-slate-50 focus:bg-indigo-50/60 focus:outline-none"
            >
              <td className="py-2.5 pr-4 tabular-nums text-slate-400">{r.run_id}</td>
              <td className="whitespace-nowrap py-2.5 pr-4 text-slate-600">{fmtDate(r.created_at)}</td>
              <td className="whitespace-nowrap py-2.5 pr-4 text-slate-700">
                {DB_LABELS[r.db_type] ?? r.db_type} <span className="text-slate-400">· {r.db_name}</span>
              </td>
              <td className="max-w-[26rem] py-2.5 pr-4">
                <p className="truncate font-mono text-xs text-slate-800" title={r.query_text}>
                  {r.query_text}
                </p>
                <p className="mt-0.5 text-xs text-slate-400">
                  {r.problems} problem{r.problems === 1 ? "" : "s"} · {r.suggestions} suggestion{r.suggestions === 1 ? "" : "s"}
                </p>
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-slate-700">{fmtMs(r.baseline_ms)}</td>
              <td className="py-2.5 pr-4 text-right font-semibold tabular-nums text-slate-900">{fmtSpeedup(r.best_speedup)}</td>
              <td className="py-2.5">
                <Badge className={VERDICT_STYLE[r.best_verdict]}>{r.best_verdict}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
