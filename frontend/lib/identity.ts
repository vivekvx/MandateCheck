// Client-side session identity. Generated once per browser and kept in
// localStorage so the mandate form, the existing-mandates list, and the
// kill switch all agree on who "the user" is without anyone typing an ID.
// Single-user demo posture (see CLAUDE.md): this stands in for a real
// auth session, it is not one.

import { useSyncExternalStore } from "react";

const STORAGE_KEY = "mandatecheck.identity.v1";

export interface SessionIdentity {
  userId: string;
  agentId: string;
  agentDisplayName: string;
  agentPlatform: string;
}

function freshIdentity(): SessionIdentity {
  return {
    userId: `user-${crypto.randomUUID().slice(0, 8)}`,
    agentId: crypto.randomUUID(),
    agentDisplayName: "Demo Agent",
    agentPlatform: "claude",
  };
}

// Cached so repeated calls return the same object — required for
// useSyncExternalStore's getSnapshot stability, and saves localStorage reads.
let cachedIdentity: SessionIdentity | null = null;

// Client-only (reads localStorage): call from event handlers/effects, or use
// the useSessionIdentity() hook from components.
export function getSessionIdentity(): SessionIdentity {
  if (cachedIdentity) return cachedIdentity;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<SessionIdentity>;
      if (parsed.userId && parsed.agentId) {
        cachedIdentity = {
          userId: parsed.userId,
          agentId: parsed.agentId,
          agentDisplayName: parsed.agentDisplayName ?? "Demo Agent",
          agentPlatform: parsed.agentPlatform ?? "claude",
        };
        return cachedIdentity;
      }
    }
  } catch {
    // Blocked/private storage: fall through to an ephemeral identity.
  }
  const identity = freshIdentity();
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(identity));
  } catch {
    // Ephemeral is fine — everything still works within this page load.
  }
  cachedIdentity = identity;
  return identity;
}

// The identity never changes after first read, so the store never notifies.
const noopSubscribe = () => () => {};
const getServerSnapshot = () => null;

// Hydration-safe identity for components: null during prerender/hydration,
// the per-browser identity right after — no setState-in-effect involved.
export function useSessionIdentity(): SessionIdentity | null {
  return useSyncExternalStore(noopSubscribe, getSessionIdentity, getServerSnapshot);
}

export function sessionShortId(identity: SessionIdentity): string {
  return identity.agentId.slice(0, 4);
}
