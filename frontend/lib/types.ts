export type DbType = "mysql" | "postgres" | "sqlite";

export type Verdict = "Recommended" | "Optional" | "Not worth it";

export interface TableInfo {
  name: string;
  rows: number;
}

export interface ConnectRequest {
  db_type: DbType;
  host?: string;
  port?: number | null;
  user?: string | null;
  password?: string;
  database: string;
}

export interface ConnectResponse {
  session_id: string;
  db_type: DbType;
  database: string;
  tables: TableInfo[];
}

export interface PlanStep {
  table: string;
  access: string;
  access_label: string;
  index_used: string | null;
  rows_examined: number;
  full_scan: boolean;
  filesort: boolean;
}

export interface Problem {
  problem_id: number | null;
  rule_code: string;
  severity: "high" | "medium" | "low";
  table: string | null;
  title: string;
  message: string;
  columns: string[];
  drop_sql: string | null;
}

export interface Suggestion {
  suggestion_id: number;
  rank: number;
  kind: "index" | "rewrite";
  table: string;
  columns: string[];
  index_name: string;
  ddl: string;
  rewritten_query: string | null;
  reason: string;
  rule_code: string | null;
}

export interface Analysis {
  run_id: number;
  report_id: number | null;
  db_type: DbType;
  database: string;
  query: string;
  rows_examined: number;
  plan: PlanStep[];
  problems: Problem[];
  suggestions: Suggestion[];
  notes: string[];
}

export interface TestResult {
  run_id: number;
  suggestion_id: number;
  report_id: number | null;
  ddl: string;
  query_after: string;
  before_ms: number;
  after_ms: number;
  before_timings: number[];
  after_timings: number[];
  rows_before: number;
  rows_after: number;
  plan_before: string;
  plan_after: string;
  insert_rows: number;
  insert_before_ms: number;
  insert_after_ms: number;
  index_size_kb: number;
  read_share: number;
  write_share: number;
  read_saving_ms: number;
  write_penalty_ms_per_row: number;
  read_gain_pct: number;
  write_loss_pct: number;
  speedup: number | null;
  net_benefit_ms: number;
  verdict: Verdict;
}

export interface ApplyResponse {
  applied: boolean;
  sql: string;
  rewritten_query: string | null;
  message: string;
}

export interface HistoryRun {
  run_id: number;
  db_type: DbType;
  db_name: string;
  query_text: string;
  baseline_ms: number | null;
  created_at: string;
  problems: number;
  suggestions: number;
  best_verdict: Verdict | "Not tested";
  best_speedup: number | null;
}

export interface RunProblem {
  problem_id: number;
  rule_code: string;
  message: string;
  severity: "high" | "medium" | "low";
}

export interface RunSuggestion {
  suggestion_id: number;
  problem_id: number | null;
  ddl_text: string;
  reason: string;
  rank_no: number;
  result_id: number | null;
  before_ms: number | null;
  after_ms: number | null;
  rows_before: number | null;
  rows_after: number | null;
  insert_before_ms: number | null;
  insert_after_ms: number | null;
  index_size_kb: number | null;
  net_benefit_ms: number | null;
  verdict: Verdict | null;
  tested_at: string | null;
}

export interface RunDetail {
  run_id: number;
  db_type: DbType;
  db_name: string;
  query_text: string;
  baseline_ms: number | null;
  created_at: string;
  problems: RunProblem[];
  suggestions: RunSuggestion[];
  report: { report_id: number; report_text: string; created_at: string } | null;
}
