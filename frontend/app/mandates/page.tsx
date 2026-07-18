"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import MandateForm from "@/components/MandateForm";
import MandateList from "@/components/MandateList";
import {
  getSessionIdentity,
  sessionShortId,
  type SessionIdentity,
} from "@/lib/identity";

export default function MandatesPage() {
  // Loaded after mount: identity is per-browser (localStorage), so reading
  // it during render would break static-export hydration.
  const [identity, setIdentity] = useState<SessionIdentity | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    setIdentity(getSessionIdentity());
  }, []);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-sans font-semibold text-text-primary">
          Mandates
        </h1>
        <Link
          href="/"
          className="text-sm font-sans text-ink-600 dark:text-ink-400 hover:text-ink-700 dark:hover:text-ink-300"
        >
          Back
        </Link>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-sans font-medium text-ink-800 dark:text-ink-100">
          Create mandate
        </h2>
        {identity ? (
          <MandateForm
            identity={identity}
            onCreated={() => setRefreshKey((k) => k + 1)}
          />
        ) : (
          <p className="text-sm font-sans text-ink-600 dark:text-ink-400">
            Preparing your session…
          </p>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-sans font-medium text-ink-800 dark:text-ink-100">
          Existing mandates
        </h2>
        {identity && (
          <p className="text-xs font-sans text-ink-600 dark:text-ink-400">
            Agent: {identity.agentDisplayName} · Session:{" "}
            <span className="font-mono">{sessionShortId(identity)}</span>
          </p>
        )}
        <MandateList userId={identity?.userId ?? ""} refreshKey={refreshKey} />
      </section>
    </div>
  );
}
