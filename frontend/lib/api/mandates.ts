import { apiFetch } from "./client";

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
