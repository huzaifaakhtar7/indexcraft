"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import BeforeAfterChart from "@/components/BeforeAfterChart";
import CodeBlock from "@/components/CodeBlock";
import ConfirmDialog from "@/components/ConfirmDialog";
import ResultTable from "@/components/ResultTable";
import { Alert, Badge, Button, ButtonLink, Card, cx, EmptyState, Loading, PageHeader } from "@/components/ui";
import { ApiError, applySuggestion, downloadReport, errorMessage } from "@/lib/api";
import { DB_LABELS, fmtMs, fmtSize, fmtSpeedup, VERDICT_ORDER, VERDICT_STYLE } from "@/lib/format";
import { useStore } from "@/lib/store";
import type { Suggestion, TestResult, Verdict } from "@/lib/types";

const VERDICT_TEXT: Record<Verdict, string> = {
  Recommended: "Clear gain for this workload. The faster reads are worth the extra write cost.",
  Optional: "A small gain. Apply it only if this query is important to you.",
  "Not worth it": "The index does not pay for its cost on this workload. Keep the table as it is.",
};

const VERDICT_BORDER: Record<Verdict, string> = {
  Recommended: "border-l-emerald-500",
  Optional: "border-l-amber-500",
  "Not worth it": "border-l-slate-400",
};

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-slate-900">{value}</p>
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export default function ResultPage() {
  const router = useRouter();
  const { ready, connection, analysis, results, selected, select, applied, markApplied, setConnection } = useStore();
  const [dialog, setDialog] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState<"" | "text" | "json">("");

  if (!ready) return <Loading />;

  const tested: { s: Suggestion; r: TestResult }[] = (analysis?.suggestions ?? [])
    .filter((s) => results[s.suggestion_id])
    .map((s) => ({ s, r: results[s.suggestion_id] }))
    .sort((a, b) => VERDICT_ORDER[a.r.verdict] - VERDICT_ORDER[b.r.verdict] || b.r.net_benefit_ms - a.r.net_benefit_ms);

  if (!analysis || tested.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="Result" />
        <EmptyState
          title="Nothing tested yet"
          text="Analyze a query and press “Test on copy” on a suggestion. The measured result appears here."
          action={<ButtonLink href={analysis ? "/diagnosis" : "/analyze"}>{analysis ? "Go to Diagnosis" : "Go to Query"}</ButtonLink>}
        />
      </div>
    );
  }

  const current = tested.find((t) => t.s.suggestion_id === selected) ?? tested[0];
  const { s, r } = current;
  const isApplied = applied.includes(s.suggestion_id);
  const untested = analysis.suggestions.length - tested.length;
  const reportId = r.report_id ?? analysis.report_id;

  async function apply() {
    if (!connection) return;
    setApplying(true);
    setError("");
    try {
      await applySuggestion(connection.session_id, s.suggestion_id);
      markApplied(s.suggestion_id);
      setDialog(false);
    } catch (e) {
      if (e instanceof ApiError && e.sessionLost) {
        setConnection(null);
        router.push("/");
        return;
      }
      setError(errorMessage(e));
      setDialog(false);
    } finally {
      setApplying(false);
    }
  }

  async function download(format: "text" | "json") {
    if (!reportId) return;
    setDownloading(format);
    setError("");
    try {
      await downloadReport(reportId, format);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setDownloading("");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Result"
        description={
          <>
            Measured on a copy of <span className="font-medium text-slate-700">{DB_LABELS[analysis.db_type]} · {analysis.database}</span>.
            The real data was not changed.
          </>
        }
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => download("text")} loading={downloading === "text"} disabled={!reportId}>
              Download report
            </Button>
            <Button variant="secondary" onClick={() => download("json")} loading={downloading === "json"} disabled={!reportId}>
              JSON
            </Button>
          </div>
        }
      />

      {tested.length > 1 && (
        <div className="flex flex-wrap gap-2" role="tablist">
          {tested.map(({ s: ts, r: tr }, i) => (
            <button
              key={ts.suggestion_id}
              type="button"
              role="tab"
              aria-selected={ts.suggestion_id === s.suggestion_id}
              onClick={() => select(ts.suggestion_id)}
              className={cx(
                "flex items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition",
                ts.suggestion_id === s.suggestion_id
                  ? "border-indigo-300 bg-white shadow-sm ring-2 ring-indigo-500/10"
                  : "border-slate-200 bg-white/60 text-slate-600 hover:bg-white",
              )}
            >
              <span className="text-xs font-semibold text-slate-400">#{i + 1}</span>
              <span className="font-mono text-xs">{ts.index_name}</span>
              <Badge className={VERDICT_STYLE[tr.verdict]}>{tr.verdict}</Badge>
            </button>
          ))}
        </div>
      )}

      {error && <Alert kind="error" title="Something went wrong">{error}</Alert>}
      {isApplied && (
        <Alert kind="success" title="Applied to the real database">
          {s.index_name} now exists on {analysis.database}.
          {s.rewritten_query && " Remember to change the query in your application to the rewritten version."}
        </Alert>
      )}

      <section className={cx("rounded-xl border border-l-4 border-slate-200 bg-white p-5 shadow-sm", VERDICT_BORDER[r.verdict])}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-xl">
            <Badge className={cx("text-sm", VERDICT_STYLE[r.verdict])}>{r.verdict}</Badge>
            <p className="mt-2 text-sm text-slate-600">{VERDICT_TEXT[r.verdict]}</p>
          </div>
          <div className="grid grid-cols-3 gap-4 sm:gap-6">
            <Stat label="Speed-up" value={fmtSpeedup(r.speedup)} hint={`${fmtMs(r.before_ms)} → ${fmtMs(r.after_ms)}`} />
            <Stat
              label="Net benefit"
              value={`${r.net_benefit_ms > 0 ? "+" : ""}${fmtMs(r.net_benefit_ms)}`}
              hint={`per operation, ${Math.round(r.read_share * 100)}/${Math.round(r.write_share * 100)} mix`}
            />
            <Stat label="Index size" value={fmtSize(r.index_size_kb)} hint={`writes ${r.write_loss_pct > 0 ? "+" : ""}${r.write_loss_pct}%`} />
          </div>
        </div>
        <div className="mt-5 space-y-3">
          <CodeBlock code={s.ddl} />
          {s.rewritten_query && (
            <div>
              <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">And use the rewritten query</p>
              <CodeBlock code={s.rewritten_query} />
            </div>
          )}
          <p className="text-sm text-slate-500">{s.reason}</p>
        </div>
      </section>

      <div className="grid gap-6">
        <Card title="Before and after" subtitle="Same copy, same data, same query text.">
          <ResultTable result={r} />
        </Card>
        <Card title="Chart" subtitle="Bars show the median time. Switch to log scale when the gap is very large.">
          <BeforeAfterChart result={r} />
        </Card>
      </div>

      <Card
        title="Apply to the real database"
        subtitle="Creates the index on the real tables. On big tables this can take a while and may lock writes."
        actions={
          <Button
            variant={r.verdict === "Recommended" ? "primary" : "secondary"}
            onClick={() => setDialog(true)}
            disabled={isApplied || !connection}
          >
            {isApplied ? "Applied" : "Apply index"}
          </Button>
        }
      >
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600">
          <p>
            {untested > 0
              ? `${untested} more suggestion${untested > 1 ? "s" : ""} can be tested before you decide.`
              : "All suggestions for this query have been tested."}
          </p>
          <div className="flex gap-2">
            <ButtonLink href="/diagnosis" variant="secondary">Back to Diagnosis</ButtonLink>
            <ButtonLink href="/analyze" variant="ghost">New query</ButtonLink>
          </div>
        </div>
      </Card>

      <ConfirmDialog
        open={dialog}
        title="Change the real database?"
        confirmLabel="Create index"
        checkboxLabel="I understand this changes the real database, not the copy."
        loading={applying}
        onConfirm={apply}
        onClose={() => setDialog(false)}
      >
        <p>
          This runs on <span className="font-semibold text-slate-900">{DB_LABELS[analysis.db_type]} · {analysis.database}</span>:
        </p>
        <CodeBlock code={s.ddl} />
        {r.verdict !== "Recommended" && (
          <Alert kind="warning">The verdict for this index is “{r.verdict}”. It may slow down writes more than it helps reads.</Alert>
        )}
      </ConfirmDialog>
    </div>
  );
}
