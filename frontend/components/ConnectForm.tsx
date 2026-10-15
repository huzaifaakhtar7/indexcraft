"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { connect, disconnect, errorMessage, getHealth } from "@/lib/api";
import { DB_LABELS, fmtInt } from "@/lib/format";
import { useStore } from "@/lib/store";
import type { DbType } from "@/lib/types";
import { Alert, Button, ButtonLink, Card, cx } from "./ui";

const DEFAULTS: Record<DbType, { port: string; user: string; database: string }> = {
  mysql: { port: "3306", user: "root", database: "shop" },
  postgres: { port: "5432", user: "postgres", database: "shop" },
  sqlite: { port: "", user: "", database: "shop.db" },
};

const DESCRIPTIONS: Record<DbType, string> = {
  mysql: "MySQL 8 server",
  postgres: "PostgreSQL 16+ server",
  sqlite: "Local .db file, no server",
};

const inputClass =
  "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10";

function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <div className="mt-1.5">{children}</div>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export default function ConnectForm() {
  const router = useRouter();
  const { connection, setConnection } = useStore();
  const [backend, setBackend] = useState<"checking" | "ok" | "down">("checking");
  const [dbType, setDbType] = useState<DbType>("mysql");
  const [host, setHost] = useState("localhost");
  const [port, setPort] = useState(DEFAULTS.mysql.port);
  const [user, setUser] = useState(DEFAULTS.mysql.user);
  const [password, setPassword] = useState("");
  const [database, setDatabase] = useState(DEFAULTS.mysql.database);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getHealth()
      .then(() => setBackend("ok"))
      .catch(() => setBackend("down"));
  }, []);

  function chooseType(t: DbType) {
    setDbType(t);
    setPort(DEFAULTS[t].port);
    setUser(DEFAULTS[t].user);
    setDatabase(DEFAULTS[t].database);
    setPassword("");
    setError("");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (connection) await disconnect(connection.session_id).catch(() => undefined);
      const res = await connect({
        db_type: dbType,
        host: dbType === "sqlite" ? undefined : host,
        port: dbType === "sqlite" || !port ? null : Number(port),
        user: dbType === "sqlite" ? null : user,
        password: dbType === "sqlite" ? "" : password,
        database,
      });
      setPassword("");
      setConnection(res);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function leave() {
    if (!connection) return;
    setLoading(true);
    await disconnect(connection.session_id).catch(() => undefined);
    setConnection(null);
    setLoading(false);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <Card title="Database" subtitle="The password is kept in memory only. It is never saved to disk or history.">
        <form onSubmit={submit} className="space-y-5">
          <Field label="Database type" htmlFor="db_type" hint={DESCRIPTIONS[dbType]}>
            <select
              id="db_type"
              value={dbType}
              onChange={(e) => chooseType(e.target.value as DbType)}
              className={cx(inputClass, "appearance-auto pr-8 sm:max-w-xs")}
            >
              {(Object.keys(DB_LABELS) as DbType[]).map((t) => (
                <option key={t} value={t}>
                  {DB_LABELS[t]}
                </option>
              ))}
            </select>
          </Field>

          {dbType === "sqlite" ? (
            <Field label="Database file" htmlFor="database" hint="Path to the .db file. shop.db is found in backend/data.">
              <input id="database" className={inputClass} value={database} onChange={(e) => setDatabase(e.target.value)} required />
            </Field>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_7rem]">
                <Field label="Host" htmlFor="host">
                  <input id="host" className={inputClass} value={host} onChange={(e) => setHost(e.target.value)} required />
                </Field>
                <Field label="Port" htmlFor="port">
                  <input id="port" className={inputClass} value={port} inputMode="numeric" onChange={(e) => setPort(e.target.value.replace(/\D/g, ""))} />
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="User" htmlFor="user">
                  <input id="user" className={inputClass} value={user} autoComplete="username" onChange={(e) => setUser(e.target.value)} required />
                </Field>
                <Field label="Password" htmlFor="password">
                  <input
                    id="password"
                    type="password"
                    className={inputClass}
                    value={password}
                    autoComplete="current-password"
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </Field>
              </div>
              <Field label="Database" htmlFor="database">
                <input id="database" className={inputClass} value={database} onChange={(e) => setDatabase(e.target.value)} required />
              </Field>
            </div>
          )}

          {error && (
            <Alert kind="error" title="Could not connect">
              {error}
            </Alert>
          )}

          <div className="flex items-center justify-end gap-3 border-t border-slate-100 pt-4">
            <Button type="submit" loading={loading} disabled={backend === "down"}>
              {connection ? (connection.db_type === dbType ? "Reconnect" : `Switch to ${DB_LABELS[dbType]}`) : `Connect to ${DB_LABELS[dbType]}`}
            </Button>
          </div>
        </form>
      </Card>

      <div className="space-y-6">
        <Card title="Backend">
          {backend === "checking" && <p className="text-sm text-slate-500">Checking…</p>}
          {backend === "ok" && (
            <p className="flex items-center gap-2 text-sm text-slate-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500" /> FastAPI backend is running
            </p>
          )}
          {backend === "down" && (
            <Alert kind="error" title="Backend not reachable">
              Start it in the backend folder with <code className="font-mono">uvicorn main:app --reload</code>, then reload this page.
            </Alert>
          )}
        </Card>

        {connection && (
          <Card
            title={
              <span className="flex items-center gap-2">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-emerald-100 text-xs text-emerald-700">✓</span>
                Connected
              </span>
            }
            subtitle={`${DB_LABELS[connection.db_type]} · ${connection.database}`}
            actions={
              <Button variant="ghost" size="sm" onClick={leave} disabled={loading}>
                Disconnect
              </Button>
            }
          >
            <table className="w-full text-sm">
              <tbody className="divide-y divide-slate-100">
                {connection.tables.map((t) => (
                  <tr key={t.name}>
                    <td className="py-1.5 font-mono text-xs text-slate-700">{t.name}</td>
                    <td className="py-1.5 text-right tabular-nums text-slate-500">{fmtInt(t.rows)} rows</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-4">
              <ButtonLink href="/analyze">Continue to Query →</ButtonLink>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
