"use client";

import { useState, type FormEvent } from "react";
import {
  createMandateFromValues,
  parseIntent,
  type Mandate,
  type MandateValues,
} from "@/lib/api/mandates";
import type { SessionIdentity } from "@/lib/identity";

// Natural-language mandate creation. The LLM behind /mandates/parse_intent
// only PROPOSES form values; nothing is created until the user taps Create
// here, and the allow/block decision path never involves a model — see the
// invariant boundary comment on the backend endpoint.

interface IntentComposerProps {
  identity: SessionIdentity;
  onCreated?: (mandate: Mandate) => void;
  onCustomize?: (values: MandateValues) => void;
}

const WINDOW_LABELS: Record<string, string> = {
  "24h": "day",
  "7d": "week",
  "30d": "month",
};

export default function IntentComposer({
  identity,
  onCreated,
  onCustomize,
}: IntentComposerProps) {
  const [text, setText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [proposal, setProposal] = useState<MandateValues | null>(null);
  const [proposalCaps, setProposalCaps] = useState<string>("");

  async function handleParse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || parsing) return;
    setParsing(true);
    setError(null);
    setProposal(null);
    try {
      const parsed = await parseIntent(trimmed);
      setProposal({
        merchant_allowlist: parsed.merchant_allowlist.join(", "),
        category_allowlist: parsed.category_allowlist.join(", "),
        max_amount_per_txn: String(parsed.max_amount_per_txn),
        max_amount_per_window: String(parsed.max_amount_per_window),
        window_duration: parsed.window_duration,
        max_amount_total: String(parsed.max_amount_total),
        // Keep the user's own words as the mandate's original intent.
        original_intent_text: trimmed,
        user_facing_summary: parsed.user_facing_summary,
      });
      setProposalCaps(
        `₹${parsed.max_amount_per_txn.toLocaleString("en-IN")}/txn · ₹${parsed.max_amount_per_window.toLocaleString("en-IN")}/${
          WINDOW_LABELS[parsed.window_duration] ?? parsed.window_duration
        }`
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not parse that description."
      );
    } finally {
      setParsing(false);
    }
  }

  async function handleCreate() {
    if (!proposal || creating) return;
    setCreating(true);
    setError(null);
    try {
      const mandate = await createMandateFromValues(identity, proposal);
      setProposal(null);
      setText("");
      onCreated?.(mandate);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create mandate."
      );
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <form onSubmit={handleParse} className="flex items-center gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={500}
          placeholder="Or describe it: e.g. 'let my agent spend up to ₹2000 on groceries this week'"
          aria-label="Describe a mandate in plain language"
          className="w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm font-sans text-text-primary placeholder:text-ink-600 dark:placeholder:text-ink-400 focus:outline-none focus:border-verdant-500 focus:ring-2 focus:ring-verdant-500/30"
        />
        <button
          type="submit"
          disabled={parsing || !text.trim()}
          className="shrink-0 rounded-md border border-border px-3 py-2 text-sm font-sans text-ink-700 dark:text-ink-300 hover:border-ink-400 disabled:opacity-50"
        >
          {parsing ? "Parsing..." : "Parse"}
        </button>
      </form>

      {proposal && (
        <div className="flex flex-col gap-3 rounded-lg border border-verdant-500 bg-surface-raised p-4">
          <div className="flex flex-col gap-1">
            <p className="font-sans text-sm text-text-primary">
              {proposal.user_facing_summary}{" "}
              <span className="text-ink-600 dark:text-ink-400">
                Expires in 7 days.
              </span>
            </p>
            <p className="font-mono text-xs text-ink-700 dark:text-ink-300">
              {proposalCaps}
            </p>
            {(proposal.merchant_allowlist || proposal.category_allowlist) && (
              <p className="font-sans text-xs text-ink-600 dark:text-ink-400">
                {[proposal.merchant_allowlist, proposal.category_allowlist]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={creating}
              onClick={handleCreate}
              className="rounded-md bg-verdant-600 px-4 py-2 text-sm font-sans font-medium text-ink-50 hover:bg-verdant-700 disabled:opacity-50"
            >
              {creating ? "Creating..." : "Create mandate"}
            </button>
            <button
              type="button"
              disabled={creating}
              onClick={() => onCustomize?.(proposal)}
              className="rounded-md border border-border px-3 py-2 text-sm font-sans text-ink-700 dark:text-ink-300 hover:border-ink-400"
            >
              Customize
            </button>
            <button
              type="button"
              disabled={creating}
              onClick={() => setProposal(null)}
              className="rounded-md px-3 py-2 text-sm font-sans text-ink-600 dark:text-ink-400 hover:text-ink-700 dark:hover:text-ink-300"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="text-sm font-sans text-block-600 dark:text-block-500">
          {error}
        </p>
      )}
    </div>
  );
}
