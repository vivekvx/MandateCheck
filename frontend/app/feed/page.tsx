import KillSwitch from "@/components/KillSwitch";
import LiveFeed from "@/components/LiveFeed";

export default function FeedPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-6 py-10">
      <div>
        <h1 className="text-2xl font-sans font-semibold text-text-primary">
          Transaction feed
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Live decisions from the deterministic gate, and a control to revoke
          a mandate&apos;s access immediately.
        </p>
      </div>
      <KillSwitch />
      <LiveFeed />
    </main>
  );
}
