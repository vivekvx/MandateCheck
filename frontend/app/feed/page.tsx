import Link from "next/link";
import KillSwitch from "@/components/KillSwitch";
import LiveFeed from "@/components/LiveFeed";
import RunAgent from "@/components/RunAgent";
import RunDemo from "@/components/RunDemo";

export default function FeedPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-6 py-10">
      <div>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-sans font-semibold text-text-primary">
            Transaction feed
          </h1>
          <Link
            href="/mandates"
            className="text-sm font-sans text-ink-600 dark:text-ink-400 hover:text-ink-700 dark:hover:text-ink-300"
          >
            Mandates
          </Link>
        </div>
        <p className="mt-1 text-sm text-text-muted">
          Live decisions from the deterministic gate, and a control to revoke
          a mandate&apos;s access immediately.
        </p>
      </div>
      <RunDemo />
      <RunAgent />
      <KillSwitch />
      <LiveFeed />
    </main>
  );
}
