"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  fetchActiveMandates,
  revokeMandate,
  type MandateSummary,
} from "@/lib/api/transactions";
// No auth layer in this build (see CLAUDE.md scope) — scoped to the
// per-browser session identity, same one the mandate form creates under.
import { useSessionIdentity } from "@/lib/identity";

type RevokeState = "idle" | "confirming" | "revoking" | "done" | "error";

// Same easing/duration language as the homepage motion pass.
const EASE_OUT = [0.16, 1, 0.3, 1] as const;
const STATE_TRANSITION = { duration: 0.25, ease: EASE_OUT };
// Kill switch is the dramatic demo beat — the revoking state must be on
// screen long enough to read as a deliberate action, not a flicker.
const MIN_REVOKING_MS = 500;

export default function KillSwitch() {
  const identity = useSessionIdentity();
  const [mandates, setMandates] = useState<MandateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string>("");
  const [revokeState, setRevokeState] = useState<RevokeState>("idle");
  const [revokeError, setRevokeError] = useState<string | null>(null);
  const [revokedAgentName, setRevokedAgentName] = useState<string>("");
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (!identity) return;
    let cancelled = false;
    fetchActiveMandates(identity.userId)
      .then((items) => {
        if (cancelled) return;
        setMandates(items);
        setSelectedId((current) =>
          current && items.some((m) => m.mandate_id === current)
            ? current
            : (items[0]?.mandate_id ?? "")
        );
      })
      .catch(() => {
        if (!cancelled) setMandates([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [identity]);

  useEffect(() => {
    if (revokeState !== "done") return;
    const timer = setTimeout(() => setRevokeState("idle"), 4000);
    return () => clearTimeout(timer);
  }, [revokeState]);

  const handleConfirm = async () => {
    if (!selectedId) return;
    const target = mandates.find((m) => m.mandate_id === selectedId);
    setRevokeState("revoking");
    setRevokeError(null);
    const startedAt = Date.now();
    try {
      await revokeMandate(selectedId);
      const elapsed = Date.now() - startedAt;
      if (elapsed < MIN_REVOKING_MS) {
        await new Promise((r) => setTimeout(r, MIN_REVOKING_MS - elapsed));
      }
      setRevokedAgentName(target?.agent_display_name ?? "");
      setRevokeState("done");
      setMandates((prev) => {
        const remaining = prev.filter((m) => m.mandate_id !== selectedId);
        setSelectedId((current) =>
          current === selectedId ? (remaining[0]?.mandate_id ?? "") : current
        );
        return remaining;
      });
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
      ) : mandates.length === 0 &&
        revokeState !== "revoking" &&
        revokeState !== "done" ? (
        <p className="mt-4 text-sm text-text-muted">No active mandates.</p>
      ) : (
        <div className="mt-4 flex flex-col gap-3">
          {mandates.length > 0 && (
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
          )}

          <AnimatePresence mode="wait" initial={false}>
            {revokeState === "confirming" && (
              <motion.div
                key="confirming"
                initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0, transition: STATE_TRANSITION }}
                exit={{ opacity: 0, transition: { duration: 0.15 } }}
                className="flex flex-col gap-2 rounded-md border border-block-500 bg-block-100 p-3 dark:bg-block-600/10 sm:flex-row sm:items-center"
              >
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
              </motion.div>
            )}

            {revokeState === "revoking" && (
              <motion.div
                key="revoking"
                initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0, transition: STATE_TRANSITION }}
                exit={{ opacity: 0, transition: { duration: 0.15 } }}
                className="flex items-center gap-3 rounded-md border border-block-500 bg-block-100 p-3 dark:bg-block-600/10"
              >
                <span className="h-2 w-2 animate-ping rounded-full bg-block-500" />
                <p className="text-sm font-mono text-block-600 dark:text-block-500">
                  Revoking access…
                </p>
              </motion.div>
            )}

            {revokeState === "done" && (
              <motion.div
                key="done"
                initial={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1, transition: STATE_TRANSITION }}
                exit={{ opacity: 0, transition: { duration: 0.15 } }}
                className="rounded-md border border-block-500 bg-block-600 p-3"
              >
                <p className="text-sm font-mono font-semibold tracking-wide text-ink-50">
                  Access revoked
                </p>
                <p className="mt-0.5 text-sm text-ink-100">
                  {revokedAgentName || "Agent"} can no longer act on this mandate.
                </p>
              </motion.div>
            )}

            {revokeState === "error" && (
              <motion.div
                key="error"
                initial={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0, transition: STATE_TRANSITION }}
                exit={{ opacity: 0, transition: { duration: 0.15 } }}
              >
                <p className="text-sm text-block-600 dark:text-block-500">
                  {revokeError ?? "Revoke failed — try again."}
                </p>
              </motion.div>
            )}

            {(revokeState === "idle" || revokeState === "error") && (
              <motion.button
                key="revoke-button"
                type="button"
                onClick={() => setRevokeState("confirming")}
                disabled={!selectedId}
                initial={false}
                whileHover={
                  reduceMotion
                    ? undefined
                    : { scale: 1.02, transition: { type: "spring", stiffness: 300, damping: 20 } }
                }
                className="self-start rounded-md border border-block-500 px-3 py-1.5 text-sm font-medium text-block-600 hover:bg-block-100 disabled:opacity-50 dark:text-block-500 dark:hover:bg-block-600/10"
              >
                Revoke access
              </motion.button>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
