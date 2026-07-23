"use client";

import { useState } from "react";
import { runAgent } from "@/lib/api/transactions";

type RunState = "idle" | "running" | "error";

export default function RunAgent() {
  const [state, setState] = useState<RunState>("idle");
  const [error, setError] = useState<string | null>(null);

  const handleClick = async () => {
    setState("running");
    setError(null);
    try {
      await runAgent();
      setState("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent run failed — try again.");
      setState("error");
    }
  };

  return (
    <div className="rounded-lg border border-border bg-surface-raised p-4">
      <h2 className="text-lg font-medium text-text-primary">Run LLM agent</h2>
      <p className="mt-1 text-sm text-text-muted">
        A real model decides what to purchase and attempts it against the
        live gate — unscripted, tagged as agent traffic.
      </p>
      <button
        type="button"
        onClick={handleClick}
        disabled={state === "running"}
        className="mt-4 self-start rounded-md border border-relay-500 px-3 py-1.5 text-sm font-medium text-relay-600 hover:bg-relay-100 disabled:opacity-50 dark:text-relay-500 dark:hover:bg-relay-600/10"
      >
        {state === "running" ? "Agent running…" : "Run LLM agent"}
      </button>
      {state === "error" && error && (
        <p className="mt-2 text-sm text-block-600 dark:text-block-500">{error}</p>
      )}
    </div>
  );
}
