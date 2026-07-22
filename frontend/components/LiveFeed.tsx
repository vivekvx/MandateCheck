"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  connectTransactionsFeed,
  type FeedConnectionStatus,
  type TransactionBroadcast,
} from "@/lib/api/transactions";

const MAX_ENTRIES = 200;

// Same easing/duration language as the homepage motion pass — no new
// motion vocabulary introduced here.
const EASE_OUT = [0.16, 1, 0.3, 1] as const;
const CARD_TRANSITION = { duration: 0.25, ease: EASE_OUT };

const STATUS_LABEL: Record<FeedConnectionStatus, string> = {
  connecting: "Connecting…",
  open: "Live",
  closed: "Reconnecting…",
};

type Tone = "allow" | "block" | "flag";

function toneOf(entry: TransactionBroadcast): Tone {
  if (entry.decision === "block") return "block";
  if (entry.flagged) return "flag";
  return "allow";
}

const TONE_BORDER: Record<Tone, string> = {
  allow: "border-l-verdant-500",
  block: "border-l-block-500",
  flag: "border-l-flag-500",
};

function DecisionBadge({ tone }: { tone: Tone }) {
  if (tone === "flag") {
    return (
      <span className="inline-flex items-center rounded-sm border border-flag-500 bg-flag-100 px-2 py-0.5 text-xs font-mono font-medium text-flag-600 dark:bg-flag-600/20 dark:text-flag-500">
        ALLOW · FLAGGED
      </span>
    );
  }
  if (tone === "allow") {
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

// Razorpay delivery status is a second axis, distinct from the allow/block
// verdict above: a rules-engine ALLOW can still fail to reach Razorpay
// (timeout/4xx/5xx), and that must never read as a MandateCheck block.
function RazorpayBadge({
  status,
  orderId,
}: {
  status: TransactionBroadcast["razorpay_status"];
  orderId: string | null;
}) {
  if (status === "ALLOWED_AND_SENT") {
    return (
      <span className="inline-flex items-center gap-1 rounded-sm border border-verdant-400/60 bg-transparent px-2 py-0.5 text-xs font-mono text-verdant-700 dark:text-verdant-400">
        → Razorpay: sent{orderId ? ` (${orderId})` : ""}
      </span>
    );
  }
  if (status === "RAZORPAY_ERROR") {
    return (
      <span className="inline-flex items-center gap-1 rounded-sm border border-amber-500/60 bg-transparent px-2 py-0.5 text-xs font-mono text-amber-600 dark:text-amber-400">
        → Razorpay: delivery failed
      </span>
    );
  }
  return null; // BLOCKED: the BLOCK badge already says everything needed
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-10 text-center">
      <span className="relative flex h-2.5 w-2.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-verdant-400 opacity-75" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-verdant-500" />
      </span>
      <p className="text-sm text-text-muted">
        Watching for agent activity in real time.
      </p>
    </div>
  );
}

export default function LiveFeed() {
  const [entries, setEntries] = useState<TransactionBroadcast[]>([]);
  const [status, setStatus] = useState<FeedConnectionStatus>("connecting");
  const seenIds = useRef<Set<string>>(new Set());
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    const disconnect = connectTransactionsFeed((broadcast) => {
      if (seenIds.current.has(broadcast.transaction_id)) return;
      seenIds.current.add(broadcast.transaction_id);
      setEntries((prev) => [broadcast, ...prev].slice(0, MAX_ENTRIES));
    }, setStatus);

    return disconnect;
  }, []);

  const entryMotion = reduceMotion
    ? { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 } }
    : {
        initial: { opacity: 0, y: -12, scale: 0.98 },
        animate: { opacity: 1, y: 0, scale: 1 },
        exit: { opacity: 0, scale: 0.98, transition: { duration: 0.15 } },
      };

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
        <EmptyState />
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          <AnimatePresence initial={false}>
            {entries.map((entry) => {
              const tone = toneOf(entry);
              return (
                <motion.li
                  key={entry.transaction_id}
                  layout={!reduceMotion}
                  initial={entryMotion.initial}
                  animate={entryMotion.animate}
                  exit={entryMotion.exit}
                  transition={CARD_TRANSITION}
                  className={`flex flex-col gap-1.5 border-l-4 px-4 py-3 ${TONE_BORDER[tone]}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <DecisionBadge tone={tone} />
                      <RazorpayBadge
                        status={entry.razorpay_status}
                        orderId={entry.razorpay_order_id}
                      />
                      <span className="font-mono text-sm font-medium text-text-primary">
                        {entry.merchant_id ?? "unknown merchant"}
                      </span>
                      {entry.proposed_amount != null && (
                        <span className="font-mono text-sm text-text-muted">
                          ₹{entry.proposed_amount.toLocaleString("en-IN")}
                        </span>
                      )}
                    </div>
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
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}
