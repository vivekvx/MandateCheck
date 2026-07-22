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
}

export type FeedConnectionStatus = "connecting" | "open" | "closed";

const MAX_RECONNECT_DELAY_MS = 10_000;

export function connectTransactionsFeed(
  onMessage: (broadcast: TransactionBroadcast) => void,
  onStatusChange?: (status: FeedConnectionStatus) => void
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
        const parsed = JSON.parse(event.data) as TransactionBroadcast;
        onMessage(parsed);
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
