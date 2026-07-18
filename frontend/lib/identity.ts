// Client-side session identity. Generated once per browser and kept in
// localStorage so the mandate form, the existing-mandates list, and the
// kill switch all agree on who "the user" is without anyone typing an ID.
// Single-user demo posture (see CLAUDE.md): this stands in for a real
// auth session, it is not one.

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

// Call from client code only (useEffect), never during render — the value
// is per-browser, which would break static-export hydration.
export function getSessionIdentity(): SessionIdentity {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<SessionIdentity>;
      if (parsed.userId && parsed.agentId) {
        return {
          userId: parsed.userId,
          agentId: parsed.agentId,
          agentDisplayName: parsed.agentDisplayName ?? "Demo Agent",
          agentPlatform: parsed.agentPlatform ?? "claude",
        };
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
  return identity;
}

export function sessionShortId(identity: SessionIdentity): string {
  return identity.agentId.slice(0, 4);
}
