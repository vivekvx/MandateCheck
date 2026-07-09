import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-start justify-center px-6">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
        <h1 className="text-3xl font-sans font-semibold text-text-primary">
          MandateCheck
        </h1>
        <p className="text-base font-sans text-text-muted">
          A deterministic gate that checks every AI-agent payment request
          against a user-defined mandate before it executes.
        </p>
        <nav className="flex gap-4 pt-2">
          <Link
            href="/mandates"
            className="rounded-md bg-verdant-600 px-4 py-2 text-sm font-sans font-medium text-ink-50 hover:bg-verdant-700"
          >
            Mandates
          </Link>
          <Link
            href="/feed"
            className="rounded-md border border-border px-4 py-2 text-sm font-sans font-medium text-ink-700 dark:text-ink-200 hover:border-ink-400"
          >
            Live feed
          </Link>
        </nav>
      </div>
    </div>
  );
}
