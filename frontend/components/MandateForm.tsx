"use client";

import { useState, type FormEvent } from "react";
import { createMandate, type Mandate } from "@/lib/api/mandates";
import { sessionShortId, type SessionIdentity } from "@/lib/identity";

interface MandateFormProps {
  // Auto-generated per browser (lib/identity.ts) — the form never asks
  // for user_id/agent_id; they're injected into the payload at submit.
  identity: SessionIdentity;
  // Optional prefill (e.g. a template's values) applied over the demo
  // defaults after mount.
  initialValues?: Partial<FormState>;
  onCreated?: (mandate: Mandate) => void;
}

export interface FormState {
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

// datetime-local wants local "YYYY-MM-DDTHH:mm", no timezone suffix
export function toDatetimeLocal(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate()
  )}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// Demo-friendly defaults so the form is submittable with one click on stage.
// Pure client-side prefill of form state — the payload sent to the backend is
// still whatever the fields contain at submit time, and every field stays
// editable. Computed per call so "Expires at" is always now+7d.
function makeDemoDefaults(): FormState {
  return {
    ...initialState,
    expires_at: toDatetimeLocal(new Date(Date.now() + 7 * 24 * 3600 * 1000)),
    window_duration: "24h",
    max_amount_per_txn: "25",
    max_amount_per_window: "100",
    max_amount_total: "500",
    merchant_allowlist: "amazon, flipkart, uber",
    category_allowlist: "shopping, travel",
    original_intent_text:
      "Approved for routine household shopping and travel bookings under $25 per transaction.",
    user_facing_summary: "Household shopping and travel, up to $25 per order.",
  };
}

// Every field in the backend's MandateCreate schema is required, so every
// form field validates as required here. Order matters: it's the order
// errors are reported and focused in — keep it in sync with app/schemas.py.
// (user_id/agent_id are also required by the schema but come from the
// session identity, not the form.)
const REQUIRED_FIELDS: [keyof FormState, string][] = [
  ["expires_at", "Expires at"],
  ["window_duration", "Window duration"],
  ["max_amount_per_txn", "Max amount per transaction"],
  ["max_amount_per_window", "Max amount per window"],
  ["max_amount_total", "Max amount total"],
  ["merchant_allowlist", "Merchant allowlist"],
  ["category_allowlist", "Category allowlist"],
  ["start_hour", "Start hour"],
  ["end_hour", "End hour"],
  ["original_intent_text", "Original intent"],
  ["user_facing_summary", "User-facing summary"],
];

const labelClass = "font-sans text-sm text-ink-700 dark:text-ink-300";
const inputClass =
  "w-full rounded-md border border-border bg-surface-raised px-3 py-2 text-sm font-sans text-text-primary placeholder:text-ink-600 dark:placeholder:text-ink-400 focus:outline-none focus:border-verdant-500 focus:ring-2 focus:ring-verdant-500/30";
const numericInputClass = `${inputClass} font-mono`;
const invalidClass =
  "border-block-500 focus:border-block-500 focus:ring-block-500/30";
const fieldWrapClass = "flex flex-col gap-1";

export default function MandateForm({
  identity,
  initialValues,
  onCreated,
}: MandateFormProps) {
  // Lazy-initialized with the (time-dependent) demo defaults. Safe under
  // static export: this component only mounts client-side, after the page's
  // identity gate resolves — it never appears in prerendered HTML.
  const [form, setForm] = useState<FormState>(() => ({
    ...makeDemoDefaults(),
    ...initialValues,
  }));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<
    Partial<Record<keyof FormState, string>>
  >({});
  const [created, setCreated] = useState<Mandate | null>(null);

  function resetToDemoDefaults() {
    setForm(makeDemoDefaults());
    setFieldErrors({});
    setError(null);
    setCreated(null);
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    setFieldErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  function cls(key: keyof FormState, base: string) {
    return fieldErrors[key] ? `${base} ${invalidClass}` : base;
  }

  function fieldError(key: keyof FormState) {
    const message = fieldErrors[key];
    if (!message) return null;
    return (
      <p role="alert" className="text-xs font-sans text-block-600 dark:text-block-500">
        {message}
      </p>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setCreated(null);

    const errors: Partial<Record<keyof FormState, string>> = {};
    for (const [key, label] of REQUIRED_FIELDS) {
      if (!form[key].trim()) {
        errors[key] = `${label} is required.`;
      }
    }
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      const firstInvalid = REQUIRED_FIELDS.find(([key]) => errors[key]);
      if (firstInvalid) {
        document.getElementById(firstInvalid[0])?.focus();
      }
      return;
    }
    setFieldErrors({});
    setSubmitting(true);

    try {
      const mandate = await createMandate({
        user_id: identity.userId,
        agent_id: identity.agentId,
        agent_display_name: identity.agentDisplayName,
        agent_platform: identity.agentPlatform,
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
      setForm(makeDemoDefaults());
      onCreated?.(mandate);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create mandate.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs font-sans text-ink-600 dark:text-ink-400">
        Agent: {identity.agentDisplayName} · Session:{" "}
        <span className="font-mono">{sessionShortId(identity)}</span>
      </p>

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="expires_at">
              Expires at
            </label>
            <input
              id="expires_at"
              type="datetime-local"
              className={cls("expires_at", numericInputClass)}
              value={form.expires_at}
              onChange={(e) => update("expires_at", e.target.value)}
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.expires_at)}
            />
            {fieldError("expires_at")}
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="window_duration">
              Window duration
            </label>
            <input
              id="window_duration"
              className={cls("window_duration", numericInputClass)}
              placeholder="7d, 24h, 30m"
              value={form.window_duration}
              onChange={(e) => update("window_duration", e.target.value)}
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.window_duration)}
            />
            {fieldError("window_duration")}
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="max_amount_per_txn">
              Max amount per transaction
            </label>
            <input
              id="max_amount_per_txn"
              type="number"
              step="0.01"
              className={cls("max_amount_per_txn", numericInputClass)}
              value={form.max_amount_per_txn}
              onChange={(e) => update("max_amount_per_txn", e.target.value)}
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.max_amount_per_txn)}
            />
            {fieldError("max_amount_per_txn")}
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="max_amount_per_window">
              Max amount per window
            </label>
            <input
              id="max_amount_per_window"
              type="number"
              step="0.01"
              className={cls("max_amount_per_window", numericInputClass)}
              value={form.max_amount_per_window}
              onChange={(e) => update("max_amount_per_window", e.target.value)}
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.max_amount_per_window)}
            />
            {fieldError("max_amount_per_window")}
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="max_amount_total">
              Max amount total
            </label>
            <input
              id="max_amount_total"
              type="number"
              step="0.01"
              className={cls("max_amount_total", numericInputClass)}
              value={form.max_amount_total}
              onChange={(e) => update("max_amount_total", e.target.value)}
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.max_amount_total)}
            />
            {fieldError("max_amount_total")}
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="merchant_allowlist">
              Merchant allowlist
            </label>
            <input
              id="merchant_allowlist"
              className={cls("merchant_allowlist", inputClass)}
              placeholder="amazon, uber, ..."
              value={form.merchant_allowlist}
              onChange={(e) => update("merchant_allowlist", e.target.value)}
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.merchant_allowlist)}
            />
            {fieldError("merchant_allowlist")}
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass} htmlFor="category_allowlist">
              Category allowlist
            </label>
            <input
              id="category_allowlist"
              className={cls("category_allowlist", inputClass)}
              placeholder="shopping, travel, ..."
              value={form.category_allowlist}
              onChange={(e) => update("category_allowlist", e.target.value)}
              aria-required="true"
              aria-invalid={Boolean(fieldErrors.category_allowlist)}
            />
            {fieldError("category_allowlist")}
          </div>
          <div className={fieldWrapClass}>
            <label className={labelClass}>Allowed time window</label>
            <div className="flex items-center gap-2">
              <input
                id="start_hour"
                type="number"
                min={0}
                max={23}
                className={cls("start_hour", numericInputClass)}
                value={form.start_hour}
                onChange={(e) => update("start_hour", e.target.value)}
                aria-label="Start hour"
                aria-required="true"
                aria-invalid={Boolean(fieldErrors.start_hour)}
              />
              <span className="text-ink-600 dark:text-ink-400 text-sm font-sans">
                to
              </span>
              <input
                id="end_hour"
                type="number"
                min={0}
                max={23}
                className={cls("end_hour", numericInputClass)}
                value={form.end_hour}
                onChange={(e) => update("end_hour", e.target.value)}
                aria-label="End hour"
                aria-required="true"
                aria-invalid={Boolean(fieldErrors.end_hour)}
              />
            </div>
            {fieldError("start_hour")}
            {fieldError("end_hour")}
          </div>
        </div>

        <div className={fieldWrapClass}>
          <label className={labelClass} htmlFor="original_intent_text">
            Original intent
          </label>
          <textarea
            id="original_intent_text"
            className={cls("original_intent_text", inputClass)}
            rows={3}
            value={form.original_intent_text}
            onChange={(e) => update("original_intent_text", e.target.value)}
            aria-required="true"
            aria-invalid={Boolean(fieldErrors.original_intent_text)}
          />
          {fieldError("original_intent_text")}
        </div>

        <div className={fieldWrapClass}>
          <label className={labelClass} htmlFor="user_facing_summary">
            User-facing summary
          </label>
          <textarea
            id="user_facing_summary"
            className={cls("user_facing_summary", inputClass)}
            rows={2}
            value={form.user_facing_summary}
            onChange={(e) => update("user_facing_summary", e.target.value)}
            aria-required="true"
            aria-invalid={Boolean(fieldErrors.user_facing_summary)}
          />
          {fieldError("user_facing_summary")}
        </div>

        {error && (
          <p className="text-sm font-sans text-block-600 dark:text-block-500">
            {error}
          </p>
        )}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-verdant-600 px-4 py-2 text-sm font-sans font-medium text-ink-50 hover:bg-verdant-700 disabled:opacity-50"
          >
            {submitting ? "Creating..." : "Create mandate"}
          </button>
          <button
            type="button"
            onClick={resetToDemoDefaults}
            className="rounded-md border border-border px-3 py-2 text-sm font-sans text-ink-700 dark:text-ink-300 hover:border-ink-400"
          >
            Reset to demo defaults
          </button>
        </div>
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
