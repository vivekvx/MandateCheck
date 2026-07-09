"use client";

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { listMandates, type Mandate, type MandateStatus } from "@/lib/api/mandates";

interface MandateListProps {
  userId: string;
  pageSize?: number;
  refreshKey?: number;
}

const statusStyles: Record<MandateStatus, string> = {
  // Calm/neutral: deliberately not verdant. Verdant is reserved for
  // "allow" transaction outcomes on the live feed, not mandate status.
  active:
    "bg-ink-100 text-ink-700 border-ink-300 dark:bg-ink-800 dark:text-ink-200 dark:border-ink-600",
  revoked:
    "bg-block-100 text-block-600 border-block-500 dark:bg-block-600/20 dark:text-block-500",
  expired:
    "bg-flag-100 text-flag-600 border-flag-500 dark:bg-flag-600/20 dark:text-flag-500",
};

function StatusBadge({ status }: { status: MandateStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-sans font-medium ${statusStyles[status]}`}
    >
      {status}
    </span>
  );
}

export default function MandateList({
  userId,
  pageSize = 10,
  refreshKey,
}: MandateListProps) {
  const [items, setItems] = useState<Mandate[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setOffset(0);
  }, [userId, refreshKey]);

  useEffect(() => {
    if (!userId) {
      setItems([]);
      setTotal(0);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    listMandates(userId, pageSize, offset)
      .then((res) => {
        if (cancelled) return;
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Failed to load mandates.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [userId, pageSize, offset, refreshKey]);

  if (!userId) {
    return (
      <p className="text-sm font-sans text-ink-600 dark:text-ink-400">
        Enter a user ID to see their mandates.
      </p>
    );
  }

  const hasPrev = offset > 0;
  const hasNext = offset + pageSize < total;

  return (
    <div className="flex flex-col gap-3">
      {loading && (
        <p className="text-sm font-sans text-ink-600 dark:text-ink-400">
          Loading mandates...
        </p>
      )}

      {error && (
        <p className="text-sm font-sans text-block-600 dark:text-block-500">
          {error}
        </p>
      )}

      {!loading && !error && items.length === 0 && (
        <p className="text-sm font-sans text-ink-600 dark:text-ink-400">
          No mandates found.
        </p>
      )}

      <ul className="flex flex-col divide-y divide-ink-200 dark:divide-ink-700">
        {items.map((mandate) => (
          <li
            key={mandate.mandate_id}
            className="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="flex flex-col gap-0.5">
              <span className="font-sans text-sm text-text-primary">
                {mandate.agent_display_name}
                <span className="ml-2 font-mono text-xs text-ink-600 dark:text-ink-400">
                  {mandate.agent_platform}
                </span>
              </span>
              <span className="font-mono text-xs text-ink-600 dark:text-ink-400">
                {mandate.mandate_id}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-sm text-ink-700 dark:text-ink-300">
                {mandate.max_amount_per_txn}/txn
              </span>
              <StatusBadge status={mandate.status} />
            </div>
          </li>
        ))}
      </ul>

      {total > pageSize && (
        <div className="flex items-center justify-between pt-2">
          <button
            type="button"
            disabled={!hasPrev}
            onClick={() => setOffset((prev) => Math.max(0, prev - pageSize))}
            className="rounded-md border border-border px-3 py-1 text-sm font-sans text-ink-700 dark:text-ink-200 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="font-mono text-xs text-ink-600 dark:text-ink-400">
            {offset + 1}-{Math.min(offset + pageSize, total)} of {total}
          </span>
          <button
            type="button"
            disabled={!hasNext}
            onClick={() => setOffset((prev) => prev + pageSize)}
            className="rounded-md border border-border px-3 py-1 text-sm font-sans text-ink-700 dark:text-ink-200 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
