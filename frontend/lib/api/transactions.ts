const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Derive the WS scheme from API_BASE_URL's scheme rather than hardcoding
// ws://. Deployed backend (Render) is https://, so this becomes wss:// —
// required since browsers block insecure ws:// connections from an https
// page. NEXT_PUBLIC_WS_BASE_URL remains a manual override if ever needed.
const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_BASE_URL ??
  API_BASE_URL.replace(/^https:/, "wss:").replace(/^http:/, "ws:");

export type RazorpayStatus = "ALLOWED_AND_SENT" | "BLOCKED" | "RAZORPAY_ERROR";

export interface TransactionBroadcast {
  type?: "transaction";
  mandate_id: string;
  transaction_id: string;
  decision: "allow" | "block";
  reason: string;
  flagged: boolean;
  flag_reason: string | null;
  timestamp: string;
  merchant_id: string;
  proposed_amount: number;
  razorpay_status: RazorpayStatus;
  razorpay_order_id: string | null;
  source: string;
  llm_review_flagged: boolean;
  llm_advisory_note: string | null;
}

// A full transaction broadcast; or, fired later (only for llm_review_flagged
// blocks), a lightweight patch carrying just the advisory note once the
// non-binding LLM call finishes — the decision itself was already final and
// broadcast before this ever fires.
export type AdvisoryUpdate = {
  type: "advisory_update";
  transaction_id: string;
  llm_advisory_note: string;
};

export type FeedConnectionStatus = "connecting" | "open" | "closed";

const MAX_RECONNECT_DELAY_MS = 10_000;

export function connectTransactionsFeed(
  onMessage: (broadcast: TransactionBroadcast) => void,
  onStatusChange?: (status: FeedConnectionStatus) => void,
  onAdvisoryUpdate?: (update: AdvisoryUpdate) => void
): () => void {
  let socket: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectDelay = 1_000;
  let stopped = false;

  const connect = () => {
    if (stopped) return;
    onStatusChange?.("connecting");
    socket = new WebSocket(`${WS_BASE_URL}/ws/transactions`);

    socket.onopen = () => {
      reconnectDelay = 1_000;
      onStatusChange?.("open");
    };

    socket.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as
          | TransactionBroadcast
          | AdvisoryUpdate;
        if (parsed.type === "advisory_update") {
          onAdvisoryUpdate?.(parsed);
        } else {
          onMessage(parsed);
        }
      } catch {
        // malformed frame, ignore
      }
    };

    socket.onclose = () => {
      onStatusChange?.("closed");
      if (stopped) return;
      reconnectTimer = setTimeout(connect, reconnectDelay);
      reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY_MS);
    };

    socket.onerror = () => {
      socket?.close();
    };
  };

  connect();

  return () => {
    stopped = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    socket?.close();
  };
}

export async function fetchRecentTransactions(
  limit = 50
): Promise<TransactionBroadcast[]> {
  const res = await fetch(
    `${API_BASE_URL}/transactions?${new URLSearchParams({ limit: String(limit) })}`
  );
  if (!res.ok) {
    throw new Error(`failed to fetch transactions: ${res.status}`);
  }
  const data = await res.json();
  return data.items as TransactionBroadcast[];
}

export interface MandateSummary {
  mandate_id: string;
  user_id: string;
  agent_display_name: string;
  agent_platform: string;
  status: string;
}

export async function fetchActiveMandates(
  userId: string
): Promise<MandateSummary[]> {
  const res = await fetch(
    `${API_BASE_URL}/mandates?${new URLSearchParams({ user_id: userId, limit: "100" })}`
  );
  if (!res.ok) {
    throw new Error(`failed to fetch mandates: ${res.status}`);
  }
  const data = await res.json();
  return (data.items as MandateSummary[]).filter((m) => m.status === "active");
}

export async function revokeMandate(mandateId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/mandates/${mandateId}/revoke`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`failed to revoke mandate: ${res.status}`);
  }
}

// Resolves only once the backend has finished firing the whole scripted
// sequence through /evaluate_transaction (each transaction already arrived
// individually via the WebSocket feed by then) — the caller just needs this
// to know when to re-enable the button.
export async function runDemo(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/demo/run`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`failed to run demo: ${res.status}`);
  }
}

// Resolves once the LLM agent loop finishes (each of its purchase attempts
// already arrived individually via the WebSocket feed by then).
export async function runAgent(): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/agent/run`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`failed to run agent: ${res.status}`);
  }
}
