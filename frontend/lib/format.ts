import type { DbType, Verdict } from "./types";

export const DB_LABELS: Record<DbType, string> = {
  mysql: "MySQL",
  postgres: "PostgreSQL",
  sqlite: "SQLite",
};

export function fmtMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "–";
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  if (ms >= 100) return `${ms.toFixed(0)} ms`;
  if (ms >= 10) return `${ms.toFixed(1)} ms`;
  return `${ms.toFixed(2)} ms`;
}

export function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined) return "–";
  return Math.round(n).toLocaleString("en-US");
}

export function fmtSize(kb: number | null | undefined): string {
  if (kb === null || kb === undefined) return "–";
  if (kb >= 1024) return `${(kb / 1024).toFixed(1)} MB`;
  return `${fmtInt(kb)} KB`;
}

export function fmtChange(before: number, after: number): string {
  if (!before) return "–";
  const pct = ((after - before) / before) * 100;
  const shown = Math.abs(pct) >= 99.95 && Math.abs(pct) < 100 ? pct.toFixed(3) : pct.toFixed(1);
  return `${pct > 0 ? "+" : ""}${shown}%`;
}

export function fmtSpeedup(x: number | null | undefined): string {
  if (!x) return "–";
  return x >= 10 ? `${Math.round(x).toLocaleString("en-US")}×` : `${x.toFixed(1)}×`;
}

export function fmtDate(value: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("en-GB", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export const VERDICT_ORDER: Record<string, number> = { Recommended: 0, Optional: 1, "Not worth it": 2 };

export const VERDICT_STYLE: Record<Verdict | "Not tested", string> = {
  Recommended: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  Optional: "bg-amber-50 text-amber-700 ring-amber-600/20",
  "Not worth it": "bg-slate-100 text-slate-600 ring-slate-500/20",
  "Not tested": "bg-white text-slate-500 ring-slate-300",
};

export const SEVERITY_STYLE: Record<string, string> = {
  high: "bg-red-50 text-red-700 ring-red-600/20",
  medium: "bg-amber-50 text-amber-700 ring-amber-600/20",
  low: "bg-sky-50 text-sky-700 ring-sky-600/20",
};
