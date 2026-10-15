import { SEVERITY_STYLE } from "@/lib/format";
import type { Problem } from "@/lib/types";
import CodeBlock from "./CodeBlock";
import { Badge } from "./ui";

export default function ProblemCard({ problem }: { problem: Problem }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-slate-900 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-white">{problem.rule_code}</span>
        <h3 className="text-sm font-semibold text-slate-900">{problem.title}</h3>
        <Badge className={SEVERITY_STYLE[problem.severity]}>{problem.severity}</Badge>
        {problem.table && <span className="ml-auto font-mono text-xs text-slate-400">{problem.table}</span>}
      </div>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">{problem.message}</p>
      {problem.drop_sql && <CodeBlock code={problem.drop_sql} className="mt-3" />}
    </article>
  );
}
