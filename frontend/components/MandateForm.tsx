"use client";

import { useState, type FormEvent } from "react";
import { createMandate, type Mandate } from "@/lib/api/mandates";

interface MandateFormProps {
  onCreated?: (mandate: Mandate) => void;
}

interface FormState {
  user_id: string;
  agent_id: string;
  agent_display_name: string;
  agent_platform: string;
  expires_at: string;
  max_amount_per_txn: string;
  max_amount_per_window: string;
  window_duration: string;
  max_amount_total: string;
  merchant_allowlist: string;
  category_allowlist: string;
  start_hour: string;
  end_hour: string;
  original_intent_text: string;
  user_facing_summary: string;
}

const initialState: FormState = {
  user_id: "",
  agent_id: "",
  agent_display_name: "",
  agent_platform: "",
  expires_at: "",
  max_amount_per_txn: "",
  max_amount_per_window: "",
  window_duration: "",
  max_amount_total: "",
  merchant_allowlist: "",
  category_allowlist: "",
  start_hour: "0",
  end_hour: "23",
  original_intent_text: "",
  user_facing_summary: "",
};

const labelClass = "font-sans text-sm text-ink-700 dark:text-ink-300";
const inputClass =
  "w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm font-sans text-text-primary placeholder:text-ink-600 dark:placeholder:text-ink-400 focus:outline-none focus:border-verdant-500 focus:ring-2 focus:ring-verdant-500/30";
const numericInputClass = `${inputClass} font-mono`;
const fieldWrapClass = "flex flex-col gap-1";

export default function MandateForm({ onCreated }: MandateFormProps) {
  const [form, setForm] = useState<FormState>(initialState);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Mandate | null>(null);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setCreated(null);

    try {
      const mandate = await createMandate({
        user_id: form.user_id,
        agent_id: form.agent_id,
        agent_display_name: form.agent_display_name,
        agent_platform: form.agent_platform,
        expires_at: new Date(form.expires_at).toISOString(),
        max_amount_per_txn: Number(form.max_amount_per_txn),
        max_amount_per_window: Number(form.max_amount_per_window),
        window_duration: form.window_duration,
        max_amount_total: Number(form.max_amount_total),
        merchant_allowlist: form.merchant_allowlist
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean),
        category_allowlist: form.category_allowlist
          .split(",")
          .map((v) => v.trim())
          .filter(Boolean),
        allowed_time_window: {
          start_hour: Number(form.start_hour),
          end_hour: Number(form.end_hour),
        },
        original_intent_text: form.original_intent_text,
        user_facing_summary: form.user_facing_summary,
      });
      setCreated(mandate);
      setForm(initialState);
      onCreated?.(mandate);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create mandate.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="user_id">
              User ID
            </label>
            <input
              id="user_id"
              className={numericInputClass}
              value={form.user_id}
              onChange={(e) => update("user_id", e.target.value)}
              required
            />
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="agent_id">
              Agent ID
            </label>
            <input
              id="agent_id"
              className={numericInputClass}
              value={form.agent_id}
              onChange={(e) => update("agent_id", e.target.value)}
              required
            />
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="agent_display_name">
              Agent display name
            </label>
            <input
              id="agent_display_name"
              className={inputClass}
              value={form.agent_display_name}
              onChange={(e) => update("agent_display_name", e.target.value)}
              required
            />
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="agent_platform">
              Agent platform
            </label>
            <input
              id="agent_platform"
              className={inputClass}
              placeholder="chatgpt, claude, ..."
              value={form.agent_platform}
              onChange={(e) => update("agent_platform", e.target.value)}
              required
            />
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="expires_at">
              Expires at
            </label>
            <input
              id="expires_at"
              type="datetime-local"
              className={numericInputClass}
              value={form.expires_at}
              onChange={(e) => update("expires_at", e.target.value)}
              required
            />
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="window_duration">
              Window duration
            </label>
            <input
              id="window_duration"
              className={numericInputClass}
              placeholder="7d, 24h, 30m"
              value={form.window_duration}
              onChange={(e) => update("window_duration", e.target.value)}
              required
            />
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="max_amount_per_txn">
              Max amount per transaction
            </label>
            <input
              id="max_amount_per_txn"
              type="number"
              step="0.01"
              className={numericInputClass}
              value={form.max_amount_per_txn}
              onChange={(e) => update("max_amount_per_txn", e.target.value)}
              required
            />
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="max_amount_per_window">
              Max amount per window
            </label>
            <input
              id="max_amount_per_window"
              type="number"
              step="0.01"
              className={numericInputClass}
              value={form.max_amount_per_window}
              onChange={(e) => update("max_amount_per_window", e.target.value)}
              required
            />
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="max_amount_total">
              Max amount total
            </label>
            <input
              id="max_amount_total"
              type="number"
              step="0.01"
              className={numericInputClass}
              value={form.max_amount_total}
              onChange={(e) => update("max_amount_total", e.target.value)}
              required
            />
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="merchant_allowlist">
              Merchant allowlist
            </label>
            <input
              id="merchant_allowlist"
              className={inputClass}
              placeholder="amazon, uber, ..."
              value={form.merchant_allowlist}
              onChange={(e) => update("merchant_allowlist", e.target.value)}
              required
            />
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="category_allowlist">
              Category allowlist
            </label>
            <input
              id="category_allowlist"
              className={inputClass}
              placeholder="shopping, travel, ..."
              value={form.category_allowlist}
              onChange={(e) => update("category_allowlist", e.target.value)}
              required
            />
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass}>Allowed time window</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={0}
                max={23}
                className={numericInputClass}
                value={form.start_hour}
                onChange={(e) => update("start_hour", e.target.value)}
                aria-label="Start hour"
                required
              />
              <span className="text-ink-600 dark:text-ink-400 text-sm font-sans">
                to
              </span>
              <input
                type="number"
                min={0}
                max={23}
                className={numericInputClass}
                value={form.end_hour}
                onChange={(e) => update("end_hour", e.target.value)}
                aria-label="End hour"
                required
              />
            </div>
          </div>
        </div>

        <div className={fieldWrapClass}>
          <label className={labelClass} htmlFor="original_intent_text">
            Original intent
          </label>
          <textarea
            id="original_intent_text"
            className={inputClass}
            rows={3}
            value={form.original_intent_text}
            onChange={(e) => update("original_intent_text", e.target.value)}
            required
          />
        </div>

        <div className={fieldWrapClass}>
          <label className={labelClass} htmlFor="user_facing_summary">
            User-facing summary
          </label>
          <textarea
            id="user_facing_summary"
            className={inputClass}
            rows={2}
            value={form.user_facing_summary}
            onChange={(e) => update("user_facing_summary", e.target.value)}
            required
          />
        </div>

        {error && (
          <p className="text-sm font-sans text-block-600 dark:text-block-500">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="self-start rounded-md bg-verdant-600 px-4 py-2 text-sm font-sans font-medium text-ink-50 hover:bg-verdant-700 disabled:opacity-50"
        >
          {submitting ? "Creating..." : "Create mandate"}
        </button>
      </form>

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
