"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DB_LABELS } from "@/lib/format";
import { useStore } from "@/lib/store";
import { cx } from "./ui";

export default function Nav() {
  const pathname = usePathname();
  const { connection, analysis, results, ready } = useStore();
  const tested = Object.keys(results).length > 0;

  const steps = [
    { href: "/", label: "Connect", enabled: true, done: Boolean(connection) },
    { href: "/analyze", label: "Query", enabled: Boolean(connection), done: Boolean(analysis) },
    { href: "/diagnosis", label: "Diagnosis", enabled: Boolean(analysis), done: tested },
    { href: "/result", label: "Result", enabled: tested, done: false },
  ];

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-600 text-sm font-bold text-white">IC</span>
          <span className="text-base font-semibold tracking-tight text-slate-900">IndexCraft</span>
        </Link>

        <nav className="order-3 flex w-full items-center gap-1 overflow-x-auto sm:order-none sm:w-auto">
          {steps.map((s, i) => {
            const active = pathname === s.href;
            const enabled = ready && s.enabled;
            const content = (
              <>
                <span
                  className={cx(
                    "grid h-5 w-5 place-items-center rounded-full text-[11px] font-semibold",
                    active ? "bg-indigo-600 text-white" : s.done && enabled ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500",
                  )}
                >
                  {s.done && enabled && !active ? "✓" : i + 1}
                </span>
                {s.label}
              </>
            );
            const base = "flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium";
            return enabled ? (
              <Link key={s.href} href={s.href} className={cx(base, active ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100")}>
                {content}
              </Link>
            ) : (
              <span key={s.href} className={cx(base, "cursor-not-allowed text-slate-400")} aria-disabled="true">
                {content}
              </span>
            );
          })}
          <span className="mx-2 h-5 w-px shrink-0 bg-slate-200" />
          <Link
            href="/history"
            className={cx(
              "shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium",
              pathname.startsWith("/history") ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100",
            )}
          >
            History
          </Link>
        </nav>

        <div className="ml-auto">
          {ready && connection ? (
            <Link
              href="/"
              className="flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-800"
            >
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              {DB_LABELS[connection.db_type]} · {connection.database}
            </Link>
          ) : (
            <span className="flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-500">
              <span className="h-2 w-2 rounded-full bg-slate-300" />
              Not connected
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
