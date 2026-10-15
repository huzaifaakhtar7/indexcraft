"use client";

import { useState } from "react";
import { cx } from "./ui";

export default function CodeBlock({ code, className }: { code: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code.endsWith(";") ? code : `${code};`);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  }

  return (
    <div className={cx("group relative rounded-lg bg-slate-900", className)}>
      <pre className="whitespace-pre-wrap px-4 py-3 pr-20 font-mono text-[13px] leading-relaxed text-slate-100 [overflow-wrap:anywhere]">
        <code>{code.endsWith(";") ? code : `${code};`}</code>
      </pre>
      <button
        type="button"
        onClick={copy}
        className="absolute right-2 top-2 rounded-md bg-white/10 px-2 py-1 text-xs font-medium text-slate-200 transition hover:bg-white/20"
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}
