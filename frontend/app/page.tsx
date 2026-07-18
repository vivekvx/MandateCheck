"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

/*
  Home hero: the hero is itself a live-demo teaser.
  - Canvas background of drifting transaction tokens (constant activity).
  - Floating annotations around a central "SEE IT LIVE" node.
  - Click simulates one transaction being evaluated and BLOCKED, using
    the same visual language as the real feed (badge, red border, reason).
  Hero-only; /feed and /mandates untouched.
*/

const TOKENS = [
  "$25.00", "$180.00", "$9.99", "$42.50", "BLOCK", "ALLOW", "ALLOW",
  "0x4f2a", "0x91cc", "0xe03b", "cap $50", "txn_8842", "txn_1039",
  "$310.00", "ALLOW", "0x77d1", "$4.20", "mnd_2210", "BLOCK", "$67.00",
];

type Particle = {
  text: string;
  x: number; // 0..1 of width
  y: number; // px
  speed: number; // px per second
  size: number;
  kind: "ink" | "green" | "red";
};

function makeParticle(text: string, heightPx: number, randomY: boolean): Particle {
  const kind = text === "BLOCK" ? "red" : text === "ALLOW" ? "green" : "ink";
  return {
    text,
    x: Math.random(),
    y: randomY ? Math.random() * heightPx : heightPx + 20,
    speed: 8 + Math.random() * 14,
    size: 10 + Math.random() * 4,
    kind,
  };
}

function TokenCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dark = window.matchMedia("(prefers-color-scheme: dark)");
    let particles: Particle[] = [];
    let raf = 0;
    let last = performance.now();

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const { clientWidth: w, clientHeight: h } = canvas;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      particles = Array.from({ length: 48 }, (_, i) =>
        makeParticle(TOKENS[i % TOKENS.length], h, true)
      );
    };

    const colors = () =>
      dark.matches
        ? { ink: "rgba(151,161,156,0.16)", green: "rgba(85,166,141,0.22)", red: "rgba(185,79,79,0.20)" }
        : { ink: "rgba(69,75,71,0.14)", green: "rgba(47,138,111,0.20)", red: "rgba(161,63,63,0.18)" };

    const tick = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      const c = colors();
      for (const p of particles) {
        p.y -= p.speed * dt;
        if (p.y < -20) Object.assign(p, makeParticle(p.text, h, false));
        ctx.font = `${p.size}px var(--font-geist-mono), monospace`;
        ctx.fillStyle = c[p.kind];
        ctx.fillText(p.text, p.x * w, p.y);
      }
      raf = requestAnimationFrame(tick);
    };

    resize();
    raf = requestAnimationFrame(tick);
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className="absolute inset-0 h-full w-full"
    />
  );
}

function Annotation({
  label,
  className,
  lineClassName,
  delay,
}: {
  label: string;
  className: string;
  lineClassName: string;
  delay: string;
}) {
  return (
    <div
      className={`pointer-events-none absolute hidden items-center gap-0 opacity-0 md:flex hero-annotation ${className}`}
      style={{ animationDelay: delay }}
    >
      <span className="whitespace-nowrap rounded-sm border border-border bg-surface-raised px-2.5 py-1 font-mono text-[11px] tracking-widest text-text-muted">
        {label}
      </span>
      <span className={`block bg-ink-400/60 ${lineClassName}`} />
    </div>
  );
}

type DemoState = "idle" | "evaluating" | "blocked";

export default function Home() {
  const [demo, setDemo] = useState<DemoState>("idle");

  const runDemo = () => {
    if (demo !== "idle") return;
    setDemo("evaluating");
    setTimeout(() => setDemo("blocked"), 900);
  };

  return (
    <main className="relative flex flex-1 flex-col overflow-hidden">
      <TokenCanvas />

      <section className="relative mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center px-6 py-16">
        <p className="font-mono text-xs tracking-[0.3em] text-text-muted">
          MANDATECHECK
        </p>
        <h1 className="mt-3 text-center text-3xl font-semibold text-text-primary">
          A deterministic gate for AI-agent payments
        </h1>

        {/* Fixed-height stage so the demo card never shifts layout. */}
        <div className="relative mt-10 flex min-h-[340px] w-full flex-col items-center">
          {demo === "idle" && (
            <>
              <Annotation
            label="EVERY TRANSACTION CHECKED"
            className="left-[4%] top-[8%] flex-row"
            lineClassName="h-px w-16"
            delay="0.3s"
          />
          <Annotation
            label="ZERO LLM IN THE DECISION"
            className="right-[3%] top-[22%] flex-row-reverse"
            lineClassName="h-px w-16"
            delay="0.7s"
          />
          <Annotation
            label="BLOCKED IN REAL TIME"
            className="bottom-[6%] left-[8%] flex-row"
            lineClassName="h-px w-12"
            delay="1.1s"
          />
            </>
          )}

          {demo === "idle" && (
            <button
              onClick={runDemo}
              className="hero-pulse mt-16 rounded-full border border-verdant-500 bg-verdant-600 px-8 py-8 font-mono text-sm font-medium tracking-widest text-ink-50 transition-transform hover:scale-105"
            >
              SEE IT LIVE
            </button>
          )}

          {demo === "evaluating" && (
            <div className="mt-16 flex flex-col items-center gap-3 py-8">
              <span className="font-mono text-xs tracking-widest text-text-muted">
                EVALUATING txn_8842 AGAINST MANDATE mnd_2210…
              </span>
              <span className="h-1.5 w-1.5 animate-ping rounded-full bg-verdant-500" />
            </div>
          )}

          {demo === "blocked" && (
            <div className="hero-card-in mt-10 w-full max-w-md rounded-lg border border-block-500 bg-surface-raised p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center rounded-sm border border-block-500 bg-block-100 px-2 py-0.5 font-mono text-xs font-medium text-block-600 dark:bg-block-600/20 dark:text-block-500">
                  BLOCK
                </span>
                <span className="font-mono text-xs text-text-muted">just now</span>
              </div>
              <p className="mt-2 text-sm text-text-primary">
                Amount $180.00 exceeds per-transaction cap of $50.00.
              </p>
              <div className="mt-2 flex flex-wrap gap-x-4 font-mono text-xs text-text-muted">
                <span>mandate: mnd_2210</span>
                <span>txn: txn_8842</span>
              </div>
              <div className="mt-4 flex gap-3">
                <Link
                  href="/feed"
                  className="rounded-md bg-verdant-600 px-4 py-2 text-sm font-medium text-ink-50 hover:bg-verdant-700"
                >
                  Watch the live feed
                </Link>
                <Link
                  href="/mandates"
                  className="rounded-md border border-border px-4 py-2 text-sm font-medium text-ink-700 hover:border-ink-400 dark:text-ink-200"
                >
                  Set a mandate
                </Link>
              </div>
            </div>
          )}
        </div>

        <h2 className="mt-12 text-center font-serif text-4xl leading-tight text-text-primary md:text-5xl">
          The agent suggests.
          <br />
          The rules decide.
        </h2>
      </section>
    </main>
  );
}
