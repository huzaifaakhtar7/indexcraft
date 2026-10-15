"use client";

import { useEffect, useState } from "react";
import HistoryTable from "@/components/HistoryTable";
import { Alert, Button, ButtonLink, Card, cx, EmptyState, Loading, PageHeader } from "@/components/ui";
import { errorMessage, getHistory, getStats } from "@/lib/api";
import { DB_LABELS, fmtSpeedup } from "@/lib/format";
import type { DbType, HistoryRun, HistoryStats } from "@/lib/types";

const FILTERS: ("" | DbType)[] = ["", "mysql", "postgres", "sqlite"];

export default function HistoryPage() {
  const [filter, setFilter] = useState<"" | DbType>("");
  const [runs, setRuns] = useState<HistoryRun[] | null>(null);
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let alive = true;
    setRuns(null);
    setError("");
    Promise.all([getHistory(filter), getStats()])
      .then(([r, s]) => {
        if (!alive) return;
        setRuns(r);
        setStats(s);
      })
      .catch((e) => alive && setError(errorMessage(e)));
    return () => {
      alive = false;
    };
  }, [filter, reload]);

  const tested = runs?.filter((r) => r.best_verdict !== "Not tested").length ?? 0;
  const recommended = runs?.filter((r) => r.best_verdict === "Recommended").length ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="History"
        description="Every analysis is saved in the tool's own database (indexcraft_meta, 5 tables). Click a row to reopen it."
        actions={
          <Button variant="secondary" onClick={() => setReload((n) => n + 1)}>
            Refresh
          </Button>
        }
      />

      <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-sm font-medium shadow-sm" role="tablist">
        {FILTERS.map((f) => (
          <button
            key={f || "all"}
            type="button"
            role="tab"
            aria-selected={filter === f}
            onClick={() => setFilter(f)}
            className={cx("rounded-md px-3 py-1.5", filter === f ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-50")}
          >
            {f ? DB_LABELS[f] : "All databases"}
          </button>
        ))}
      </div>

      {error && <Alert kind="error" title="Could not load history">{error}</Alert>}
      {!error && runs === null && <Loading text="Loading history..." />}

      {runs && runs.length === 0 && (
        <EmptyState
          title="No analyses yet"
          text={filter ? `Nothing saved for ${DB_LABELS[filter]} yet.` : "Analyze a query and it will be saved here."}
          action={<ButtonLink href="/analyze">Analyze a query</ButtonLink>}
        />
      )}

      {runs && runs.length > 0 && (
        <>
          <div className="grid grid-cols-3 gap-3 sm:gap-4">
            {[
              { label: "Analyses", value: runs.length.toLocaleString("en-US") },
              { label: "Tested on a copy", value: tested.toLocaleString("en-US") },
              { label: "Recommended fixes", value: recommended.toLocaleString("en-US") },
            ].map((s) => (
              <div key={s.label} className="rounded-xl border border-slate-200 bg-white px-3 py-3 shadow-sm sm:px-5 sm:py-4">
                <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500 sm:text-xs">{s.label}</p>
                <p className="mt-1 text-xl sm:text-2xl font-semibold tabular-nums text-slate-900">{s.value}</p>
              </div>
            ))}
          </div>

          <Card title="Past analyses" subtitle={`${runs.length} run${runs.length === 1 ? "" : "s"}, newest first`}>
            <HistoryTable runs={runs} />
          </Card>

          {stats && stats.speedup_by_rule.length > 0 && (
            <Card title="Average speed-up per rule" subtitle="All databases. JOIN of problems, suggestions and test results with GROUP BY.">
              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {stats.speedup_by_rule.map((r) => (
                  <div key={r.rule_code} className="rounded-lg border border-slate-200 px-3 py-2.5">
                    <p className="font-mono text-xs font-semibold text-slate-500">{r.rule_code}</p>
                    <p className="mt-0.5 text-lg font-semibold tabular-nums text-slate-900">{fmtSpeedup(r.avg_speedup)}</p>
                    <p className="text-xs text-slate-500">
                      {r.cases} case{r.cases === 1 ? "" : "s"}
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
