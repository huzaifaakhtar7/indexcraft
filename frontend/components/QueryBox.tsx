"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { analyze, ApiError, errorMessage } from "@/lib/api";
import { DB_LABELS } from "@/lib/format";
import { SAMPLES } from "@/lib/samples";
import { useStore } from "@/lib/store";
import { Alert, Button, Card, cx } from "./ui";

export default function QueryBox() {
  const router = useRouter();
  const { connection, query, setQuery, readShare, setReadShare, setAnalysis, setConnection } = useStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!connection) return null;
  const samples = SAMPLES[connection.db_type];
  const reads = Math.round(readShare * 100);

  async function run() {
    if (!connection || !query.trim()) return;
    setLoading(true);
    setError("");
    try {
      const result = await analyze(connection.session_id, query);
      setAnalysis(result);
      router.push("/diagnosis");
    } catch (e) {
      if (e instanceof ApiError && e.sessionLost) {
        setConnection(null);
        router.push("/");
        return;
      }
      setError(errorMessage(e));
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <Card
        title="Slow query"
        subtitle={`Paste one SELECT statement. It runs on ${DB_LABELS[connection.db_type]} · ${connection.database}.`}
      >
        <label htmlFor="query" className="sr-only">
          SQL query
        </label>
        <textarea
          id="query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) run();
          }}
          rows={8}
          spellCheck={false}
          placeholder="SELECT * FROM orders WHERE customer_id = 500"
          className="block w-full resize-y rounded-lg border border-slate-300 bg-slate-50 px-4 py-3 font-mono text-sm leading-relaxed text-slate-900 shadow-inner outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
        />

        <div className="mt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Sample queries</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {samples.map((s) => (
              <button
                key={s.label}
                type="button"
                onClick={() => setQuery(s.query)}
                className={cx(
                  "rounded-full border px-3 py-1 text-xs font-medium transition",
                  query === s.query
                    ? "border-indigo-300 bg-indigo-50 text-indigo-700"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50",
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="mt-4">
            <Alert kind="error" title="Analysis failed">
              {error}
            </Alert>
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
          <p className="text-xs text-slate-500">
            Only a single SELECT is accepted. Press <kbd className="rounded border border-slate-300 px-1">Ctrl</kbd> +{" "}
            <kbd className="rounded border border-slate-300 px-1">Enter</kbd> to analyze.
          </p>
          <Button onClick={run} loading={loading} disabled={!query.trim()}>
            {loading ? "Reading the plan..." : "Analyze query"}
          </Button>
        </div>
      </Card>

      <div className="space-y-6">
        <Card title="Workload mix" subtitle="Used to weigh faster reads against slower writes.">
          <div className="flex items-baseline justify-between text-sm">
            <span className="font-semibold text-slate-900">{reads}% reads</span>
            <span className="text-slate-500">{100 - reads}% writes</span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={reads}
            onChange={(e) => setReadShare(Number(e.target.value) / 100)}
            aria-label="Share of reads"
            className="mt-3 w-full accent-indigo-600"
          />
          <div className="mt-3 flex gap-2">
            {[
              { label: "Read-heavy", value: 0.9 },
              { label: "Balanced", value: 0.5 },
              { label: "Write-heavy", value: 0.2 },
            ].map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => setReadShare(p.value)}
                className={cx(
                  "flex-1 whitespace-nowrap rounded-md border px-1.5 py-1 text-xs font-medium",
                  Math.abs(readShare - p.value) < 0.001
                    ? "border-indigo-300 bg-indigo-50 text-indigo-700"
                    : "border-slate-200 text-slate-600 hover:bg-slate-50",
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
        </Card>

        <Card title="What happens next">
          <ol className="space-y-2 text-sm text-slate-600">
            <li><span className="font-semibold text-slate-900">1.</span> The database explains its plan (EXPLAIN).</li>
            <li><span className="font-semibold text-slate-900">2.</span> Rules R1–R7 find what makes it slow.</li>
            <li><span className="font-semibold text-slate-900">3.</span> You test each fix on a safe copy.</li>
          </ol>
        </Card>
      </div>
    </div>
  );
}
