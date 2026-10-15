"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import CodeBlock from "@/components/CodeBlock";
import ProblemCard from "@/components/ProblemCard";
import SuggestionCard from "@/components/SuggestionCard";
import { Alert, Badge, Button, ButtonLink, Card, EmptyState, Loading, PageHeader, Spinner } from "@/components/ui";
import { ApiError, errorMessage, testSuggestion } from "@/lib/api";
import { DB_LABELS, fmtInt } from "@/lib/format";
import { useStore } from "@/lib/store";

function useElapsed(running: boolean) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!running) return;
    setSeconds(0);
    const started = Date.now();
    const id = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(id);
  }, [running]);
  return seconds;
}

export default function DiagnosisPage() {
  const router = useRouter();
  const { ready, connection, analysis, results, readShare, addResult, select, setConnection } = useStore();
  const [testing, setTesting] = useState<number[]>([]);
  const [current, setCurrent] = useState<number | null>(null);
  const [error, setError] = useState("");
  const elapsed = useElapsed(current !== null);

  if (!ready) return <Loading />;
  if (!analysis || !connection) {
    return (
      <div className="space-y-6">
        <PageHeader title="Diagnosis" />
        <EmptyState
          title="No query analyzed yet"
          text="Paste a slow query on the Query screen. Its problems and suggested fixes appear here."
          action={<ButtonLink href={connection ? "/analyze" : "/"}>{connection ? "Go to Query" : "Go to Connect"}</ButtonLink>}
        />
      </div>
    );
  }

  const a = analysis;
  const session = connection.session_id;
  const busy = current !== null;
  const untested = a.suggestions.filter((s) => !results[s.suggestion_id]);

  async function run(ids: number[]) {
    setTesting(ids);
    setError("");
    let last: number | null = null;
    for (const id of ids) {
      setCurrent(id);
      try {
        const r = await testSuggestion(session, id, readShare);
        addResult(r);
        last = id;
      } catch (e) {
        if (e instanceof ApiError && e.sessionLost) {
          setConnection(null);
          router.push("/");
          return;
        }
        setError(errorMessage(e));
        break;
      }
    }
    setCurrent(null);
    setTesting([]);
    if (last !== null && ids.length === 1) router.push("/result");
  }

  const position = current !== null ? testing.indexOf(current) + 1 : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Diagnosis"
        description={`${DB_LABELS[a.db_type]} · ${a.database} · ${a.problems.length} problem${a.problems.length === 1 ? "" : "s"} · ${a.suggestions.length} suggestion${a.suggestions.length === 1 ? "" : "s"}`}
        actions={<ButtonLink href="/analyze" variant="secondary">Change query</ButtonLink>}
      />

      <Card title="Query">
        <CodeBlock code={a.query} />
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[32rem] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-4 font-medium">Table</th>
                <th className="py-2 pr-4 font-medium">How it is read</th>
                <th className="py-2 pr-4 font-medium">Index used</th>
                <th className="py-2 text-right font-medium">Rows examined</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {a.plan.map((step, i) => (
                <tr key={`${step.table}-${i}`}>
                  <td className="py-2 pr-4 font-mono text-xs text-slate-700">{step.table}</td>
                  <td className="py-2 pr-4">
                    <span className={step.full_scan ? "font-medium text-red-700" : "text-slate-700"}>{step.access_label}</span>
                    {step.filesort && <Badge className="ml-2 bg-amber-50 text-amber-700 ring-amber-600/20">extra sort</Badge>}
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs text-slate-500">{step.index_used ?? "none"}</td>
                  <td className="py-2 text-right tabular-nums text-slate-900">{fmtInt(step.rows_examined)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {busy && (
        <Alert kind="info">
          <span className="flex items-center gap-2">
            <Spinner />
            Testing {testing.length > 1 ? `suggestion ${position} of ${testing.length}` : "the suggestion"} on a copy of the data · {elapsed}s.
            Copying a large table and building the index can take a minute.
          </span>
        </Alert>
      )}
      {error && <Alert kind="error" title="Test failed">{error}</Alert>}

      <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">What is wrong</h2>
          {a.problems.length === 0 ? (
            <Alert kind="success" title="No problem found">The query already uses an index well.</Alert>
          ) : (
            a.problems.map((p, i) => <ProblemCard key={`${p.rule_code}-${i}`} problem={p} />)
          )}
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Suggested fixes</h2>
            {a.suggestions.length > 1 && (
              <Button size="sm" variant="secondary" onClick={() => run(untested.map((s) => s.suggestion_id))} disabled={busy || untested.length === 0}>
                Test all ({untested.length})
              </Button>
            )}
          </div>
          {a.suggestions.length === 0 && (
            <Alert kind="info" title="No index suggestion">An index cannot help this query. See the notes below.</Alert>
          )}
          {a.suggestions.map((s) => (
            <SuggestionCard
              key={s.suggestion_id}
              suggestion={s}
              result={results[s.suggestion_id]}
              testing={current === s.suggestion_id}
              disabled={busy}
              onTest={() => run([s.suggestion_id])}
              onView={() => {
                select(s.suggestion_id);
                router.push("/result");
              }}
            />
          ))}
          {a.notes.length > 0 && (
            <Card title="Notes">
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
                {a.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </Card>
          )}
          {Object.keys(results).length > 0 && !busy && (
            <div className="flex justify-end">
              <ButtonLink href="/result">See results →</ButtonLink>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
