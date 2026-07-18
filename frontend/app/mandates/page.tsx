"use client";

import { useState } from "react";
import Link from "next/link";
import IntentComposer from "@/components/IntentComposer";
import MandateForm, { type FormState } from "@/components/MandateForm";
import MandateList from "@/components/MandateList";
import TemplatePicker from "@/components/TemplatePicker";
import { sessionShortId, useSessionIdentity } from "@/lib/identity";

export default function MandatesPage() {
  // null during prerender/hydration, per-browser identity right after —
  // useSyncExternalStore keeps this hydration-safe without effects.
  const identity = useSessionIdentity();
  const [refreshKey, setRefreshKey] = useState(0);
  // Templates are the default view; the full form sits behind
  // "Custom mandate" (blank) or a card's "Customize" (prefilled).
  const [view, setView] = useState<"templates" | "custom">("templates");
  const [customPrefill, setCustomPrefill] = useState<
    Partial<FormState> | undefined
  >(undefined);

  const onCreated = () => setRefreshKey((k) => k + 1);

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
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-sans font-medium text-ink-800 dark:text-ink-100">
            Create mandate
          </h2>
          {view === "templates" ? (
            <button
              type="button"
              onClick={() => {
                setCustomPrefill(undefined);
                setView("custom");
              }}
              className="text-sm font-sans text-ink-600 dark:text-ink-400 hover:text-ink-700 dark:hover:text-ink-300"
            >
              Custom mandate
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setView("templates")}
              className="text-sm font-sans text-ink-600 dark:text-ink-400 hover:text-ink-700 dark:hover:text-ink-300"
            >
              Back to templates
            </button>
          )}
        </div>

        {!identity ? (
          <p className="text-sm font-sans text-ink-600 dark:text-ink-400">
            Preparing your session…
          </p>
        ) : view === "templates" ? (
          <div className="flex flex-col gap-4">
            <IntentComposer
              identity={identity}
              onCreated={onCreated}
              onCustomize={(values) => {
                setCustomPrefill(values);
                setView("custom");
              }}
            />
            <TemplatePicker
              identity={identity}
              onCreated={onCreated}
              onCustomize={(values) => {
                setCustomPrefill(values);
                setView("custom");
              }}
            />
          </div>
        ) : (
          <MandateForm
            // Remount when the prefill changes so template values land in
            // the mount-time prefill effect.
            key={customPrefill ? JSON.stringify(customPrefill) : "blank"}
            identity={identity}
            initialValues={customPrefill}
            onCreated={onCreated}
          />
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
        <MandateList
          // Remount on identity/refresh change: resets pagination without a
          // state-syncing effect inside the list.
          key={`${identity?.userId ?? "none"}:${refreshKey}`}
          userId={identity?.userId ?? ""}
        />
      </section>
    </div>
  );
}
