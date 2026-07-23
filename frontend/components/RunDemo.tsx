"use client";

import { useState } from "react";
import { runDemo } from "@/lib/api/transactions";

type RunState = "idle" | "running" | "error";

export default function RunDemo() {
  const [state, setState] = useState<RunState>("idle");
  const [error, setError] = useState<string | null>(null);

  const handleClick = async () => {
    setState("running");
    setError(null);
    try {
      await runDemo();
      setState("idle");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo run failed — try again.");
      setState("error");
    }
  };

  return (
    <div className="rounded-lg border border-border bg-surface-raised p-4">
      <h2 className="text-lg font-medium text-text-primary">Run demo</h2>
      <p className="mt-1 text-sm text-text-muted">
        Streams a scripted sequence of transactions through the live gate —
        real rules engine, real Razorpay calls, tagged as demo traffic.
      </p>
      <button
        type="button"
        onClick={handleClick}
        disabled={state === "running"}
        className="mt-4 self-start rounded-md border border-verdant-500 px-3 py-1.5 text-sm font-medium text-verdant-700 hover:bg-verdant-100 disabled:opacity-50 dark:text-verdant-400 dark:hover:bg-verdant-700/10"
      >
        {state === "running" ? "Running demo…" : "Run demo"}
      </button>
      {state === "error" && error && (
        <p className="mt-2 text-sm text-block-600 dark:text-block-500">{error}</p>
      )}
    </div>
  );
}
