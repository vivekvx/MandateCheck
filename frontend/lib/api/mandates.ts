import { apiFetch } from "./client";
import type { SessionIdentity } from "@/lib/identity";

export interface AllowedTimeWindow {
  start_hour: number;
  end_hour: number;
}

export type MandateStatus = "active" | "revoked" | "expired";

export interface Mandate {
  mandate_id: string;
  user_id: string;
  agent_id: string;
  agent_platform: string;
  agent_display_name: string;
  created_at: string;
  expires_at: string;
  status: MandateStatus;
  max_amount_per_txn: number;
  max_amount_per_window: number;
  window_duration: string;
  max_amount_total: number;
  merchant_allowlist: string[];
  category_allowlist: string[];
  allowed_time_window: AllowedTimeWindow;
  original_intent_text: string;
  user_facing_summary: string;
}

export interface MandateCreateInput {
  user_id: string;
  agent_id: string;
  agent_platform: string;
  agent_display_name: string;
  expires_at: string;
  max_amount_per_txn: number;
  max_amount_per_window: number;
  window_duration: string;
  max_amount_total: number;
  merchant_allowlist: string[];
  category_allowlist: string[];
  allowed_time_window: AllowedTimeWindow;
  original_intent_text: string;
  user_facing_summary: string;
}

export interface MandateListResponse {
  items: Mandate[];
  limit: number;
  offset: number;
  total: number;
}

export function createMandate(input: MandateCreateInput): Promise<Mandate> {
  return apiFetch<Mandate>("/mandates", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getMandate(mandateId: string): Promise<Mandate> {
  return apiFetch<Mandate>(`/mandates/${mandateId}`);
}

// Comma-separated string form of a mandate's editable fields — the shape
// templates and parsed intents share with the manual form's prefill.
export interface MandateValues {
  merchant_allowlist: string;
  category_allowlist: string;
  max_amount_per_txn: string;
  max_amount_per_window: string;
  window_duration: string;
  max_amount_total: string;
  original_intent_text: string;
  user_facing_summary: string;
}

// One-tap creation used by template cards and confirmed parsed intents:
// identity + values, expiry defaulted to 7 days, full-day time window.
export function createMandateFromValues(
  identity: SessionIdentity,
  values: MandateValues,
): Promise<Mandate> {
  const splitList = (v: string) =>
    v
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  return createMandate({
    user_id: identity.userId,
    agent_id: identity.agentId,
    agent_display_name: identity.agentDisplayName,
    agent_platform: identity.agentPlatform,
    expires_at: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
    max_amount_per_txn: Number(values.max_amount_per_txn),
    max_amount_per_window: Number(values.max_amount_per_window),
    window_duration: values.window_duration,
    max_amount_total: Number(values.max_amount_total),
    merchant_allowlist: splitList(values.merchant_allowlist),
    category_allowlist: splitList(values.category_allowlist),
    allowed_time_window: { start_hour: 0, end_hour: 23 },
    original_intent_text: values.original_intent_text,
    user_facing_summary: values.user_facing_summary,
  });
}

export interface ParsedIntent {
  merchant_allowlist: string[];
  category_allowlist: string[];
  max_amount_per_txn: number;
  max_amount_per_window: number;
  window_duration: string;
  max_amount_total: number;
  user_facing_summary: string;
}

// LLM-backed field proposal only — the result is shown to the user and
// nothing is created until they confirm (which goes through createMandate).
// The decision path (/evaluate_transaction) never sees this.
export function parseIntent(text: string): Promise<ParsedIntent> {
  return apiFetch<ParsedIntent>("/mandates/parse_intent", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function listMandates(
  userId: string,
  limit = 20,
  offset = 0,
): Promise<MandateListResponse> {
  const params = new URLSearchParams({
    user_id: userId,
    limit: String(limit),
    offset: String(offset),
  });
  return apiFetch<MandateListResponse>(`/mandates?${params.toString()}`);
}
