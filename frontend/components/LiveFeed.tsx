"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  connectTransactionsFeed,
  fetchRecentTransactions,
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

// Long order ids ("order_QwErTy12AbCd34Ef") get a middle-ellipsis so the
// badge never dominates the row on a narrow viewport.
function formatOrderId(id: string): string {
  if (id.length <= 20) return id;
  return `${id.slice(0, 12)}…${id.slice(-4)}`;
}

// Razorpay delivery status is a second axis, distinct from the allow/block
// verdict above: a rules-engine ALLOW can still fail to reach Razorpay
// (timeout/4xx/5xx), and that must never read as a MandateCheck block. Uses
// `relay` (steel-blue), not `flag`'s gold or `block`'s red — a delivery
// failure is a system/rail problem, not a rules-engine judgment call.
function RazorpayBadge({
  status,
  orderId,
}: {
  status: TransactionBroadcast["razorpay_status"];
  orderId: string | null;
}) {
  if (status === "ALLOWED_AND_SENT") {
    return (
      <span className="inline-flex items-center gap-1 rounded-sm border border-verdant-400 bg-verdant-100 px-2 py-0.5 text-xs font-mono font-medium text-verdant-700 dark:bg-verdant-700/20 dark:text-verdant-400">
        → Razorpay: sent{orderId ? ` (${formatOrderId(orderId)})` : ""}
      </span>
    );
  }
  if (status === "RAZORPAY_ERROR") {
    return (
      <span className="inline-flex items-center gap-1 rounded-sm border border-relay-500 bg-relay-100 px-2 py-0.5 text-xs font-mono font-medium text-relay-600 dark:bg-relay-600/20 dark:text-relay-500">
        → Razorpay: delivery failed
      </span>
    );
  }
  return null; // BLOCKED: the BLOCK badge already says everything needed
}

// Advisory-only, never a decision — deliberately not reusing block/flag/
// relay colors so it can't be misread as another verdict. amber, distinct
// from verdant (allow), block-red (block), flag-gold, and relay-blue.
function AdvisoryBadge({
  hasNote,
  expanded,
  onToggle,
}: {
  hasNote: boolean;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="inline-flex items-center gap-1 rounded-sm border border-amber-500 bg-amber-100 px-2 py-0.5 text-xs font-mono font-medium text-amber-700 hover:bg-amber-200 dark:bg-amber-600/20 dark:text-amber-400 dark:hover:bg-amber-600/30"
    >
      Flagged for review{hasNote ? (expanded ? " ▲" : " ▼") : "…"}
    </button>
  );
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
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const seenIds = useRef<Set<string>>(new Set());
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    const disconnect = connectTransactionsFeed(
      (broadcast) => {
        if (seenIds.current.has(broadcast.transaction_id)) return;
        seenIds.current.add(broadcast.transaction_id);
        setEntries((prev) => [broadcast, ...prev].slice(0, MAX_ENTRIES));
      },
      setStatus,
      (update) => {
        // Patches an already-rendered entry in place — the advisory note
        // arrives after the decision it comments on, never before.
        setEntries((prev) =>
          prev.map((entry) =>
            entry.transaction_id === update.transaction_id
              ? { ...entry, llm_advisory_note: update.llm_advisory_note }
              : entry
          )
        );
      }
    );

    // Runs independently of the WebSocket connect above: whichever arrives
    // first wins for a given transaction_id, the other is deduped via
    // seenIds so a transaction that lands right as this resolves never
    // renders twice.
    fetchRecentTransactions()
      .then((history) => {
        setEntries((prev) => {
          const merged = [...prev];
          for (const item of history) {
            if (seenIds.current.has(item.transaction_id)) continue;
            seenIds.current.add(item.transaction_id);
            merged.push(item);
          }
          return merged.slice(0, MAX_ENTRIES);
        });
      })
      .catch(() => {
        // Historical load is a nice-to-have; the live feed still works
        // without it, so a fetch failure here is silent rather than
        // blocking the page.
      });

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
                      {entry.llm_review_flagged && (
                        <AdvisoryBadge
                          hasNote={Boolean(entry.llm_advisory_note)}
                          expanded={expandedId === entry.transaction_id}
                          onToggle={() =>
                            setExpandedId((current) =>
                              current === entry.transaction_id ? null : entry.transaction_id
                            )
                          }
                        />
                      )}
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
                  {entry.llm_review_flagged &&
                    entry.llm_advisory_note &&
                    expandedId === entry.transaction_id && (
                      <p className="text-sm text-amber-700 dark:text-amber-400">
                        LLM advisory (non-binding): {entry.llm_advisory_note}
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
