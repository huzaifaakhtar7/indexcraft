"use client";

import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import CodeBlock from "@/components/CodeBlock";
import ConfirmDialog from "@/components/ConfirmDialog";
import { Alert, Badge, Button, ButtonLink, Card, EmptyState, Loading, PageHeader } from "@/components/ui";
import { deleteRun, downloadReport, errorMessage, getRun } from "@/lib/api";
import { DB_LABELS, fmtDate, fmtInt, fmtMs, fmtSize, fmtSpeedup, SEVERITY_STYLE, VERDICT_STYLE } from "@/lib/format";
import type { RunDetail } from "@/lib/types";

const REWRITE = " Rewritten query: ";

export default function RunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params);
  const id = Number(runId);
  const router = useRouter();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState("");
  const [missing, setMissing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    getRun(id)
      .then(setRun)
      .catch((e) => {
        if (e?.status === 404) setMissing(true);
        else setError(errorMessage(e));
      });
  }, [id]);

  async function remove() {
    setDeleting(true);
    try {
      await deleteRun(id);
      router.push("/history");
    } catch (e) {
      setError(errorMessage(e));
      setDeleting(false);
      setConfirm(false);
    }
  }

  if (missing) {
    return (
      <EmptyState
        title={`Run #${runId} not found`}
        text="It may have been deleted."
        action={<ButtonLink href="/history">Back to History</ButtonLink>}
      />
    );
  }
  if (error && !run) return <Alert kind="error" title="Could not load this run">{error}</Alert>;
  if (!run) return <Loading text="Loading run..." />;

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Run #${run.run_id}`}
        description={`${DB_LABELS[run.db_type] ?? run.db_type} · ${run.db_name} · ${fmtDate(run.created_at)} · baseline ${fmtMs(run.baseline_ms)}`}
        actions={
          <div className="flex gap-2">
            <ButtonLink href="/history" variant="secondary">All runs</ButtonLink>
            {run.report && (
              <Button variant="secondary" onClick={() => downloadReport(run.report!.report_id, "text").catch((e) => setError(errorMessage(e)))}>
                Download report
              </Button>
            )}
            <Button variant="danger" onClick={() => setConfirm(true)}>
              Delete
            </Button>
          </div>
        }
      />

      {error && <Alert kind="error">{error}</Alert>}

      <Card title="Query">
        <CodeBlock code={run.query_text} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Card title="Problems" subtitle={`${run.problems.length} found`}>
          {run.problems.length === 0 ? (
            <p className="text-sm text-slate-500">No problem was found for this query.</p>
          ) : (
            <ul className="space-y-3">
              {run.problems.map((p) => (
                <li key={p.problem_id}>
                  <div className="flex items-center gap-2">
                    <span className="rounded-md bg-slate-900 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-white">{p.rule_code}</span>
                    <Badge className={SEVERITY_STYLE[p.severity]}>{p.severity}</Badge>
                  </div>
                  <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{p.message}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Suggestions and test results" subtitle="One test result per suggestion">
          {run.suggestions.length === 0 ? (
            <p className="text-sm text-slate-500">No index was suggested.</p>
          ) : (
            <ul className="space-y-5">
              {run.suggestions.map((s) => {
                const [reason, rewritten] = s.reason.split(REWRITE);
                const tested = s.verdict !== null && s.before_ms !== null && s.after_ms !== null;
                return (
                  <li key={s.suggestion_id} className="border-b border-slate-100 pb-5 last:border-0 last:pb-0">
                    <div className="mb-2 flex items-center gap-2">
                      <span className="grid h-6 w-6 place-items-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-700">{s.rank_no}</span>
                      <Badge className={VERDICT_STYLE[s.verdict ?? "Not tested"]}>{s.verdict ?? "Not tested"}</Badge>
                      {tested && s.after_ms ? (
                        <span className="text-sm font-semibold text-slate-900">{fmtSpeedup(s.before_ms! / s.after_ms)} faster</span>
                      ) : null}
                    </div>
                    <CodeBlock code={s.ddl_text} />
                    {rewritten && <CodeBlock code={rewritten} className="mt-2" />}
                    <p className="mt-2 text-sm text-slate-600">{reason}</p>
                    {tested && (
                      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
                        <div>
                          <dt className="text-xs text-slate-500">Query time</dt>
                          <dd className="tabular-nums text-slate-900">{fmtMs(s.before_ms)} → {fmtMs(s.after_ms)}</dd>
                        </div>
                        <div>
                          <dt className="text-xs text-slate-500">Rows examined</dt>
                          <dd className="tabular-nums text-slate-900">{fmtInt(s.rows_before)} → {fmtInt(s.rows_after)}</dd>
                        </div>
                        <div>
                          <dt className="text-xs text-slate-500">INSERT 10k rows</dt>
                          <dd className="tabular-nums text-slate-900">{fmtMs(s.insert_before_ms)} → {fmtMs(s.insert_after_ms)}</dd>
                        </div>
                        <div>
                          <dt className="text-xs text-slate-500">Index size</dt>
                          <dd className="tabular-nums text-slate-900">{fmtSize(s.index_size_kb)}</dd>
                        </div>
                      </dl>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>

      {run.report && (
        <Card title="Report" subtitle={`Saved ${fmtDate(run.report.created_at)}`}>
          <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-4 font-mono text-xs leading-relaxed text-slate-800 ring-1 ring-inset ring-slate-200">
            {run.report.report_text}
          </pre>
        </Card>
      )}

      <ConfirmDialog
        open={confirm}
        title={`Delete run #${run.run_id}?`}
        confirmLabel="Delete run"
        danger
        loading={deleting}
        onConfirm={remove}
        onClose={() => setConfirm(false)}
      >
        <p>This removes the run with its problems, suggestions, test results and report (ON DELETE CASCADE). It cannot be undone.</p>
      </ConfirmDialog>
    </div>
  );
}
