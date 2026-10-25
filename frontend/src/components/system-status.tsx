"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, apiFetch } from "@/lib/api";

// Mirrors backend/app/schemas/health.py
type Health = {
  status: "ok" | "degraded";
  database: "ok" | "unavailable";
  migration_revision: string | null;
};

type State =
  | { kind: "loading" }
  | { kind: "ready"; health: Health; checkedAt: Date }
  | { kind: "error"; message: string; checkedAt: Date };

async function fetchHealth(): Promise<State> {
  try {
    const health = await apiFetch<Health>("/health");
    return { kind: "ready", health, checkedAt: new Date() };
  } catch (error) {
    // 503 means the API answered but the database is down.
    if (error instanceof ApiError && error.status === 503) {
      return {
        kind: "ready",
        health: { status: "degraded", database: "unavailable", migration_revision: null },
        checkedAt: new Date(),
      };
    }
    const message =
      error instanceof ApiError && error.status === 0
        ? error.message
        : "The API did not respond. Is the backend running on port 8000?";
    return { kind: "error", message, checkedAt: new Date() };
  }
}

export function SystemStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    void fetchHealth().then((next) => {
      if (!cancelled) setState(next);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const recheck = () => {
    setState({ kind: "loading" });
    void fetchHealth().then(setState);
  };

  const apiOk = state.kind === "ready";
  const dbOk = state.kind === "ready" && state.health.database === "ok";
  const revision = state.kind === "ready" ? state.health.migration_revision : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>System status</CardTitle>
        <CardDescription>
          {state.kind === "loading"
            ? "Checking…"
            : `Last checked ${state.checkedAt.toLocaleTimeString()}`}
        </CardDescription>
        <CardAction>
          <Button variant="outline" size="sm" onClick={recheck} disabled={state.kind === "loading"}>
            Check again
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-[auto_1fr] items-center gap-x-6 gap-y-3 text-sm">
          <dt className="text-muted-foreground">API</dt>
          <dd>
            <StatusBadge loading={state.kind === "loading"} ok={apiOk} okLabel="Reachable" badLabel="Unreachable" />
          </dd>
          <dt className="text-muted-foreground">Database</dt>
          <dd>
            <StatusBadge loading={state.kind === "loading"} ok={dbOk} okLabel="Connected" badLabel="Unavailable" />
          </dd>
          <dt className="text-muted-foreground">Migration</dt>
          <dd className="font-mono text-xs">
            {state.kind === "loading" ? "…" : (revision ?? "none applied")}
          </dd>
        </dl>
        {state.kind === "error" && (
          <p role="alert" className="mt-4 text-sm text-destructive">
            {state.message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function StatusBadge({
  loading,
  ok,
  okLabel,
  badLabel,
}: {
  loading: boolean;
  ok: boolean;
  okLabel: string;
  badLabel: string;
}) {
  if (loading) return <Badge variant="outline">Checking</Badge>;
  return ok ? <Badge variant="secondary">{okLabel}</Badge> : <Badge variant="destructive">{badLabel}</Badge>;
}
