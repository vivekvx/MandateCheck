"use client";

import { useState } from "react";
import { createMandate, type Mandate } from "@/lib/api/mandates";
import type { FormState } from "@/components/MandateForm";
import type { SessionIdentity } from "@/lib/identity";

export interface MandateTemplate {
  id: string;
  title: string;
  emoji: string;
  // Short human line shown on the card, e.g. "₹1,000/txn · ₹3,000/week".
  caps: string;
  merchants: string;
  values: Pick<
    FormState,
    | "max_amount_per_txn"
    | "max_amount_per_window"
    | "window_duration"
    | "max_amount_total"
    | "merchant_allowlist"
    | "category_allowlist"
    | "original_intent_text"
    | "user_facing_summary"
  >;
}

export const MANDATE_TEMPLATES: MandateTemplate[] = [
  {
    id: "grocery",
    title: "Grocery shopping",
    emoji: "🛒",
    caps: "₹1,000/txn · ₹3,000/week",
    merchants: "amazon, flipkart, bigbasket",
    values: {
      merchant_allowlist: "amazon, flipkart, bigbasket",
      category_allowlist: "shopping",
      max_amount_per_txn: "1000",
      max_amount_per_window: "3000",
      window_duration: "7d",
      max_amount_total: "12000",
      original_intent_text:
        "Approved for grocery and household shopping on amazon, flipkart and bigbasket, up to ₹1000 per transaction and ₹3000 per week.",
      user_facing_summary: "Groceries up to ₹1,000 per order, ₹3,000 a week.",
    },
  },
  {
    id: "travel",
    title: "Travel booking",
    emoji: "✈️",
    caps: "₹5,000/txn · ₹15,000/week",
    merchants: "makemytrip, uber, ola",
    values: {
      merchant_allowlist: "makemytrip, uber, ola",
      category_allowlist: "travel",
      max_amount_per_txn: "5000",
      max_amount_per_window: "15000",
      window_duration: "7d",
      max_amount_total: "60000",
      original_intent_text:
        "Approved for travel bookings and rides on makemytrip, uber and ola, up to ₹5000 per transaction and ₹15000 per week.",
      user_facing_summary: "Travel up to ₹5,000 per booking, ₹15,000 a week.",
    },
  },
  {
    id: "subscriptions",
    title: "Subscription renewals",
    emoji: "🔁",
    caps: "₹500/txn · ₹1,500/month",
    merchants: "netflix, spotify, hotstar",
    values: {
      merchant_allowlist: "netflix, spotify, hotstar",
      category_allowlist: "subscriptions",
      max_amount_per_txn: "500",
      max_amount_per_window: "1500",
      window_duration: "30d",
      max_amount_total: "6000",
      original_intent_text:
        "Approved for recurring subscription renewals, up to ₹500 per renewal and ₹1500 per month.",
      user_facing_summary: "Subscriptions up to ₹500 each, ₹1,500 a month.",
    },
  },
];

interface TemplatePickerProps {
  identity: SessionIdentity;
  onCreated?: (mandate: Mandate) => void;
  // "Customize" on a card: hand the template's values to the full form.
  onCustomize?: (values: MandateTemplate["values"]) => void;
}

export default function TemplatePicker({
  identity,
  onCreated,
  onCustomize,
}: TemplatePickerProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Mandate | null>(null);

  const selected = MANDATE_TEMPLATES.find((t) => t.id === selectedId) ?? null;

  async function confirmCreate(template: MandateTemplate) {
    setCreating(true);
    setError(null);
    try {
      const mandate = await createMandate({
        user_id: identity.userId,
        agent_id: identity.agentId,
        agent_display_name: identity.agentDisplayName,
        agent_platform: identity.agentPlatform,
        // Sensible default, never user-entered: 7 days out.
        expires_at: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
        max_amount_per_txn: Number(template.values.max_amount_per_txn),
        max_amount_per_window: Number(template.values.max_amount_per_window),
        window_duration: template.values.window_duration,
        max_amount_total: Number(template.values.max_amount_total),
        merchant_allowlist: template.values.merchant_allowlist
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean),
        category_allowlist: template.values.category_allowlist
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean),
        allowed_time_window: { start_hour: 0, end_hour: 23 },
        original_intent_text: template.values.original_intent_text,
        user_facing_summary: template.values.user_facing_summary,
      });
      setCreated(mandate);
      setSelectedId(null);
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
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {MANDATE_TEMPLATES.map((template) => {
          const isSelected = template.id === selectedId;
          return (
            <button
              key={template.id}
              type="button"
              onClick={() => {
                setSelectedId(isSelected ? null : template.id);
                setError(null);
                setCreated(null);
              }}
              aria-pressed={isSelected}
              className={`flex flex-col items-start gap-1.5 rounded-lg border p-4 text-left transition-colors ${
                isSelected
                  ? "border-verdant-500 bg-verdant-100/50 dark:bg-verdant-600/10"
                  : "border-border bg-surface-raised hover:border-ink-400 dark:hover:border-ink-500"
              }`}
            >
              <span className="text-2xl" aria-hidden="true">
                {template.emoji}
              </span>
              <span className="font-sans text-sm font-medium text-text-primary">
                {template.title}
              </span>
              <span className="font-mono text-xs text-ink-700 dark:text-ink-300">
                {template.caps}
              </span>
              <span className="font-sans text-xs text-ink-600 dark:text-ink-400">
                {template.merchants}
              </span>
            </button>
          );
        })}
      </div>

      {selected && (
        <div className="flex flex-col gap-3 rounded-lg border border-verdant-500 bg-surface-raised p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-sans text-sm text-text-primary">
            {selected.values.user_facing_summary}{" "}
            <span className="text-ink-600 dark:text-ink-400">
              Expires in 7 days.
            </span>
          </p>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              disabled={creating}
              onClick={() => confirmCreate(selected)}
              className="rounded-md bg-verdant-600 px-4 py-2 text-sm font-sans font-medium text-ink-50 hover:bg-verdant-700 disabled:opacity-50"
            >
              {creating ? "Creating..." : "Create mandate"}
            </button>
            <button
              type="button"
              disabled={creating}
              onClick={() => onCustomize?.(selected.values)}
              className="rounded-md border border-border px-3 py-2 text-sm font-sans text-ink-700 dark:text-ink-300 hover:border-ink-400"
            >
              Customize
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="text-sm font-sans text-block-600 dark:text-block-500">
          {error}
        </p>
      )}

      {created && (
        <div className="rounded-lg border border-verdant-400 bg-verdant-100 dark:bg-ink-900 dark:border-verdant-600 px-4 py-3">
          <p className="text-sm font-sans text-ink-700 dark:text-ink-200">
            Mandate created.
          </p>
          <p className="mt-1 text-base font-sans text-text-primary">
            {created.user_facing_summary}
          </p>
        </div>
      )}
    </div>
  );
}
