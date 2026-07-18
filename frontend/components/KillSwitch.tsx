"use client";

import { useEffect, useState } from "react";
import {
  fetchActiveMandates,
  revokeMandate,
  type MandateSummary,
} from "@/lib/api/transactions";
// No auth layer in this build (see CLAUDE.md scope) — scoped to the
// per-browser session identity, same one the mandate form creates under.
import { getSessionIdentity } from "@/lib/identity";

type RevokeState = "idle" | "confirming" | "revoking" | "done" | "error";

export default function KillSwitch() {
  const [mandates, setMandates] = useState<MandateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string>("");
  const [revokeState, setRevokeState] = useState<RevokeState>("idle");
  const [revokeError, setRevokeError] = useState<string | null>(null);

  const loadMandates = () => {
    setLoading(true);
    fetchActiveMandates(getSessionIdentity().userId)
      .then((items) => {
        setMandates(items);
        setSelectedId((current) =>
          current && items.some((m) => m.mandate_id === current)
            ? current
            : (items[0]?.mandate_id ?? "")
        );
      })
      .catch(() => setMandates([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadMandates();
  }, []);

  const handleConfirm = async () => {
    if (!selectedId) return;
    setRevokeState("revoking");
    setRevokeError(null);
    try {
      await revokeMandate(selectedId);
      setRevokeState("done");
      setMandates((prev) => prev.filter((m) => m.mandate_id !== selectedId));
      setSelectedId((prev) => (prev === selectedId ? "" : prev));
    } catch (err) {
      setRevokeError(err instanceof Error ? err.message : "Revoke failed — try again.");
      setRevokeState("error");
    }
  };

  const selected = mandates.find((m) => m.mandate_id === selectedId);

  return (
    <div className="rounded-lg border border-border bg-surface-raised p-4">
      <h2 className="text-lg font-medium text-text-primary">Kill switch</h2>
      <p className="mt-1 text-sm text-text-muted">
        Revoke a mandate&apos;s access immediately.
      </p>

      {loading ? (
        <p className="mt-4 text-sm text-text-muted">Loading active mandates…</p>
      ) : mandates.length === 0 ? (
        <p className="mt-4 text-sm text-text-muted">No active mandates.</p>
      ) : (
        <div className="mt-4 flex flex-col gap-3">
          <select
            aria-label="Mandate to revoke"
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-verdant-500 focus:ring-2 focus:ring-verdant-500/30"
            value={selectedId}
            disabled={revokeState === "revoking"}
            onChange={(e) => {
              setSelectedId(e.target.value);
              setRevokeState("idle");
            }}
          >
            {mandates.map((m) => (
              <option key={m.mandate_id} value={m.mandate_id}>
                {m.agent_display_name} ({m.agent_platform}) — {m.mandate_id}
              </option>
            ))}
          </select>

          {revokeState === "confirming" ? (
            <div className="flex flex-col gap-2 rounded-md border border-block-500 bg-block-100 p-3 dark:bg-block-600/10 sm:flex-row sm:items-center">
              <p className="flex-1 text-sm text-block-600 dark:text-block-500">
                Revoke access for <span className="font-mono">{selected?.agent_display_name}</span>?
                This takes effect immediately and can&apos;t be undone.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleConfirm}
                  className="shrink-0 rounded-md bg-block-600 px-3 py-1.5 text-sm font-medium text-ink-50 hover:bg-block-500"
                >
                  Confirm revoke
                </button>
                <button
                  type="button"
                  onClick={() => setRevokeState("idle")}
                  className="shrink-0 rounded-md border border-border px-3 py-1.5 text-sm text-text-primary hover:bg-ink-100 dark:hover:bg-ink-800"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setRevokeState("confirming")}
              disabled={!selectedId || revokeState === "revoking"}
              className="self-start rounded-md border border-block-500 px-3 py-1.5 text-sm font-medium text-block-600 hover:bg-block-100 disabled:opacity-50 dark:text-block-500 dark:hover:bg-block-600/10"
            >
              Revoke access
            </button>
          )}

          {revokeState === "done" && (
            <p className="text-sm font-mono text-verdant-600 dark:text-verdant-400">
              Revoked. Mandate no longer active.
            </p>
          )}
          {revokeState === "error" && (
            <p className="text-sm text-block-600 dark:text-block-500">
              {revokeError ?? "Revoke failed — try again."}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
