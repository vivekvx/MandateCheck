"use client";

import { useState } from "react";
import Link from "next/link";
import MandateForm from "@/components/MandateForm";
import MandateList from "@/components/MandateList";

export default function MandatesPage() {
  const [userId, setUserId] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

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
        <MandateForm
          onCreated={(mandate) => {
            setUserId(mandate.user_id);
            setRefreshKey((k) => k + 1);
          }}
        />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-sans font-medium text-ink-800 dark:text-ink-100">
          Existing mandates
        </h2>
        <div className="flex flex-col gap-1">
          <label
            htmlFor="filter_user_id"
            className="text-sm font-sans text-ink-700 dark:text-ink-300"
          >
            User ID
          </label>
          <input
            id="filter_user_id"
            className="w-full max-w-xs rounded-md border border-border bg-surface-raised px-3 py-2 text-sm font-mono text-text-primary placeholder:text-ink-600 dark:placeholder:text-ink-400 focus:outline-none focus:border-verdant-500 focus:ring-2 focus:ring-verdant-500/30"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            placeholder="u1"
          />
        </div>
        <MandateList userId={userId} refreshKey={refreshKey} />
      </section>
    </div>
  );
}
