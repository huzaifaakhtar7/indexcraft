import { fmtMs, fmtSpeedup, VERDICT_STYLE } from "@/lib/format";
import type { Suggestion, TestResult } from "@/lib/types";
import CodeBlock from "./CodeBlock";
import { Badge, Button } from "./ui";

interface Props {
  suggestion: Suggestion;
  result?: TestResult;
  testing: boolean;
  disabled: boolean;
  onTest: () => void;
  onView: () => void;
}

export default function SuggestionCard({ suggestion: s, result, testing, disabled, onTest, onView }: Props) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="grid h-6 w-6 place-items-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-700">{s.rank}</span>
        <h3 className="text-sm font-semibold text-slate-900">
          {s.kind === "rewrite" ? "Rewrite the query, then index" : s.columns.length > 1 ? "Composite index" : "Single-column index"}
        </h3>
        {s.rule_code && <span className="font-mono text-xs text-slate-400">fixes {s.rule_code}</span>}
        {result && <Badge className={`ml-auto ${VERDICT_STYLE[result.verdict]}`}>{result.verdict}</Badge>}
      </div>

      <CodeBlock code={s.ddl} className="mt-3" />
      {s.rewritten_query && (
        <div className="mt-3">
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">Rewritten query</p>
          <CodeBlock code={s.rewritten_query} />
        </div>
      )}
      <p className="mt-3 text-sm text-slate-600">{s.reason}</p>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3">
        {result ? (
          <p className="text-sm text-slate-600">
            <span className="font-semibold tabular-nums text-slate-900">{fmtMs(result.before_ms)}</span> →{" "}
            <span className="font-semibold tabular-nums text-slate-900">{fmtMs(result.after_ms)}</span>
            {result.speedup ? <span className="ml-2 text-slate-500">({fmtSpeedup(result.speedup)} faster)</span> : null}
          </p>
        ) : (
          <p className="text-xs text-slate-500">Not tested yet. The test copies the table and measures real time.</p>
        )}
        <div className="flex gap-2">
          {result && (
            <Button variant="secondary" size="sm" onClick={onView}>
              View result
            </Button>
          )}
          <Button size="sm" variant={result ? "ghost" : "primary"} onClick={onTest} loading={testing} disabled={disabled}>
            {testing ? "Testing on copy..." : result ? "Test again" : "Test on copy"}
          </Button>
        </div>
      </div>
    </article>
  );
}
