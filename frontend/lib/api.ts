import axios, { AxiosError } from "axios";
import type {
  Analysis,
  ApplyResponse,
  ConnectRequest,
  ConnectResponse,
  DbType,
  HistoryRun,
  HistoryStats,
  RunDetail,
  TestResult,
} from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

const api = axios.create({ baseURL: API_URL });

export class ApiError extends Error {
  status: number | null;

  constructor(message: string, status: number | null) {
    super(message);
    this.status = status;
  }

  get sessionLost() {
    return this.status === 404 && this.message.startsWith("Session not found");
  }
}

function toApiError(e: unknown): ApiError {
  if (e instanceof ApiError) return e;
  const err = e as AxiosError<{ detail?: unknown }>;
  if (!err.response) {
    return new ApiError(`The backend is not reachable at ${API_URL}. Start it with: uvicorn main:app --reload`, null);
  }
  const detail = err.response.data?.detail;
  if (typeof detail === "string") return new ApiError(detail, err.response.status);
  if (Array.isArray(detail)) {
    const text = detail
      .map((d: { loc?: (string | number)[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`)
      .join("; ");
    return new ApiError(`Invalid input. ${text}`, err.response.status);
  }
  return new ApiError(`Request failed with status ${err.response.status}`, err.response.status);
}

async function call<T>(fn: () => Promise<{ data: T }>): Promise<T> {
  try {
    return (await fn()).data;
  } catch (e) {
    throw toApiError(e);
  }
}

export function errorMessage(e: unknown): string {
  return toApiError(e).message;
}

export const getHealth = () => call<{ status: string; message: string }>(() => api.get("/health"));

export const connect = (body: ConnectRequest) => call<ConnectResponse>(() => api.post("/connect", body));

export const disconnect = (session_id: string) =>
  call<{ ok: boolean; message: string }>(() => api.post("/disconnect", { session_id }));

export const analyze = (session_id: string, query: string) =>
  call<Analysis>(() => api.post("/analyze", { session_id, query }));

export const testSuggestion = (session_id: string, suggestion_id: number, read_share: number, runs = 5) =>
  call<TestResult>(() => api.post("/test", { session_id, suggestion_id, read_share, runs }));

export const applySuggestion = (session_id: string, suggestion_id: number) =>
  call<ApplyResponse>(() => api.post("/apply", { session_id, suggestion_id, confirm: true }));

export const getHistory = (db_type?: DbType | "") =>
  call<HistoryRun[]>(() => api.get("/history", { params: db_type ? { db_type, limit: 200 } : { limit: 200 } }));

export const getStats = () => call<HistoryStats>(() => api.get("/history/stats"));

export const getRun = (run_id: number) => call<RunDetail>(() => api.get(`/history/${run_id}`));

export const deleteRun = (run_id: number) =>
  call<{ ok: boolean; message: string }>(() => api.delete(`/history/${run_id}`));

export async function downloadReport(report_id: number, format: "text" | "json") {
  const data = await call<string | object>(() =>
    api.get(`/report/${report_id}`, { params: { format }, responseType: format === "text" ? "text" : "json" }),
  );
  const body = format === "text" ? String(data) : JSON.stringify(data, null, 2);
  const blob = new Blob([body], { type: format === "text" ? "text/plain" : "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `indexcraft_report_${report_id}.${format === "text" ? "txt" : "json"}`;
  a.click();
  URL.revokeObjectURL(url);
}

export default api;
