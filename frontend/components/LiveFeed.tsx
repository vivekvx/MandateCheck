"use client";

import { useEffect, useRef, useState } from "react";
import {
  connectTransactionsFeed,
  type FeedConnectionStatus,
  type TransactionBroadcast,
} from "@/lib/api/transactions";

const MAX_ENTRIES = 200;

const STATUS_LABEL: Record<FeedConnectionStatus, string> = {
  connecting: "Connecting…",
  open: "Live",
  closed: "Reconnecting…",
};

function DecisionBadge({
  decision,
  flagged,
}: {
  decision: TransactionBroadcast["decision"];
  flagged: boolean;
}) {
  if (decision === "allow" && flagged) {
    return (
      <span className="inline-flex items-center rounded-sm border border-flag-500 bg-flag-100 px-2 py-0.5 text-xs font-mono font-medium text-flag-600 dark:bg-flag-600/20 dark:text-flag-500">
        ALLOW · FLAGGED
      </span>
    );
  }
  if (decision === "allow") {
    return (
      <span className="inline-flex items-center rounded-sm border border-verdant-400 bg-verdant-100 px-2 py-0.5 text-xs font-mono font-medium text-verdant-700 dark:bg-verdant-700/20 dark:text-verdant-400">
        ALLOW
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-sm border border-block-500 bg-block-100 px-2 py-0.5 text-xs font-mono font-medium text-block-600 dark:bg-block-600/20 dark:text-block-500">
      BLOCK
    </span>
  );
}

export default function LiveFeed() {
  const [entries, setEntries] = useState<TransactionBroadcast[]>([]);
  const [status, setStatus] = useState<FeedConnectionStatus>("connecting");
  const seenIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    const disconnect = connectTransactionsFeed((broadcast) => {
      if (seenIds.current.has(broadcast.transaction_id)) return;
      seenIds.current.add(broadcast.transaction_id);
      setEntries((prev) => [broadcast, ...prev].slice(0, MAX_ENTRIES));
    }, setStatus);

    return disconnect;
  }, []);

  return (
    <div className="rounded-lg border border-border bg-surface-raised">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-lg font-medium text-text-primary">Live feed</h2>
        <span className="flex items-center gap-2 text-xs font-mono text-text-muted">
          <span
            className={`h-2 w-2 rounded-full ${
              status === "open" ? "bg-verdant-500" : "bg-ink-400"
            }`}
          />
          {STATUS_LABEL[status]}
        </span>
      </div>

      {entries.length === 0 ? (
        <p className="px-4 py-8 text-center text-sm text-text-muted">
          Waiting for transactions…
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {entries.map((entry) => (
            <li key={entry.transaction_id} className="flex flex-col gap-1 px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <DecisionBadge decision={entry.decision} flagged={entry.flagged} />
                <span className="font-mono text-xs text-text-muted">
                  {new Date(entry.timestamp).toLocaleString()}
                </span>
              </div>
              <p className="text-sm text-text-primary">{entry.reason}</p>
              {entry.flagged && entry.flag_reason && (
                <p className="text-sm text-flag-600 dark:text-flag-500">
                  {entry.flag_reason}
                </p>
              )}
              <div className="flex flex-wrap gap-x-4 gap-y-0.5 font-mono text-xs text-text-muted">
                <span>mandate: {entry.mandate_id}</span>
                <span>txn: {entry.transaction_id}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
