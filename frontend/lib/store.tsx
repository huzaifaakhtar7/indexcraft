"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Analysis, ConnectResponse, TestResult } from "./types";

interface State {
  connection: ConnectResponse | null;
  query: string;
  readShare: number;
  analysis: Analysis | null;
  results: Record<number, TestResult>;
  applied: number[];
  selected: number | null;
}

interface Store extends State {
  ready: boolean;
  setConnection: (c: ConnectResponse | null) => void;
  setQuery: (q: string) => void;
  setReadShare: (r: number) => void;
  setAnalysis: (a: Analysis | null) => void;
  addResult: (r: TestResult) => void;
  markApplied: (suggestionId: number) => void;
  select: (suggestionId: number | null) => void;
}

const KEY = "indexcraft";

const EMPTY: State = {
  connection: null,
  query: "",
  readShare: 0.9,
  analysis: null,
  results: {},
  applied: [],
  selected: null,
};

const StoreContext = createContext<Store | null>(null);

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<State>(EMPTY);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(KEY);
      if (saved) setState({ ...EMPTY, ...JSON.parse(saved) });
    } catch {}
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    try {
      sessionStorage.setItem(KEY, JSON.stringify(state));
    } catch {}
  }, [state, ready]);

  const setConnection = useCallback((connection: ConnectResponse | null) => {
    setState((s) => ({ ...EMPTY, query: s.query, readShare: s.readShare, connection }));
  }, []);
  const setQuery = useCallback((query: string) => setState((s) => ({ ...s, query })), []);
  const setReadShare = useCallback((readShare: number) => setState((s) => ({ ...s, readShare })), []);
  const setAnalysis = useCallback(
    (analysis: Analysis | null) => setState((s) => ({ ...s, analysis, results: {}, applied: [], selected: null })),
    [],
  );
  const addResult = useCallback(
    (r: TestResult) =>
      setState((s) => ({ ...s, results: { ...s.results, [r.suggestion_id]: r }, selected: r.suggestion_id })),
    [],
  );
  const markApplied = useCallback(
    (id: number) => setState((s) => ({ ...s, applied: s.applied.includes(id) ? s.applied : [...s.applied, id] })),
    [],
  );
  const select = useCallback((selected: number | null) => setState((s) => ({ ...s, selected })), []);

  const value = useMemo(
    () => ({ ...state, ready, setConnection, setQuery, setReadShare, setAnalysis, addResult, markApplied, select }),
    [state, ready, setConnection, setQuery, setReadShare, setAnalysis, addResult, markApplied, select],
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore(): Store {
  const store = useContext(StoreContext);
  if (!store) throw new Error("useStore must be used inside StoreProvider");
  return store;
}
