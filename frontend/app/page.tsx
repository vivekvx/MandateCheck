"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  AnimatePresence,
  motion,
  useReducedMotion,
  type Variants,
} from "framer-motion";

/*
  Home hero: the hero is itself a live-demo teaser.
  - Canvas background of drifting transaction tokens (constant activity).
  - Floating annotations around a central "SEE IT LIVE" node.
  - Click simulates one transaction being evaluated and BLOCKED, using
    the same visual language as the real feed (badge, red border, reason).
  Hero-only; /feed and /mandates untouched.

  Motion pass: framer-motion layered on top for entrance stagger, scroll
  reveal, and spring hover — same colors/layout/copy as before.
*/

const EASE_OUT = [0.16, 1, 0.3, 1] as const;

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
    // Slow, ambient drift — background texture, not a foreground distraction.
    speed: 4 + Math.random() * 6,
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

// Character pool for the gate structure: hex/binary/structural glyphs, the
// same vocabulary the token canvas already drifts through the background —
// the gate reads as "built from the transactions it evaluates," not a
// borrowed figure. No words, no faces, single characters only.
const GATE_GLYPHS = ["0", "1", "#", "=", "+", "-", "$", "A", "F", "/"];

// Renders the checkpoint gate as one canvas draw (no DOM text nodes at all,
// cheaper than even a single <pre>). Static after first paint — the only
// ongoing motion on the hero backdrop is the separate scan bracket, so this
// never re-runs per frame. Shape: two tapered uprights + a lintel, with the
// aperture between them left empty — that gap is the choke point where
// "SEE IT LIVE" sits, i.e. where a transaction passes through the gate.
function GateCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dark = window.matchMedia("(prefers-color-scheme: dark)");

    const draw = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (w === 0 || h === 0) return;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const color = dark.matches ? "151,161,156" : "69,75,71";
      const accent = dark.matches ? "85,166,141" : "47,138,111";

      const cell = Math.max(6, Math.round(Math.min(w, h) * 0.012));
      const cols = Math.ceil(w / cell);
      const rows = Math.ceil(h / cell);
      ctx.font = `${cell - 1}px var(--font-geist-mono), monospace`;
      ctx.textBaseline = "middle";

      for (let row = 0; row < rows; row++) {
        const v = row / rows; // 0 top -> 1 bottom
        for (let col = 0; col < cols; col++) {
          const u = (col / cols) * 2 - 1; // -1 .. 1, 0 center

          // Uprights taper slightly narrower toward the top (architectural,
          // not a rectangle extrusion) and sit inset from the lintel/base.
          const halfWidth = 0.1 + 0.02 * v;
          const upright =
            v > 0.1 && v < 0.94 && Math.abs(Math.abs(u) - 0.5) < halfWidth;
          const lintel = v < 0.13 && Math.abs(u) < 0.62;
          const base =
            v > 0.9 && v < 0.98 && Math.abs(Math.abs(u) - 0.5) < 0.17;
          // Threshold strip across the aperture floor — the line you cross.
          const threshold = v > 0.93 && v < 0.945 && Math.abs(u) < 0.34;

          if (!upright && !lintel && !base && !threshold) continue;

          // Edge cells (near a shape boundary) render brighter/denser than
          // interior cells — an etched outline over a lighter fill, same
          // density-gradient technique as traditional ASCII-art shading.
          // Lintel/base/threshold are thin bands to begin with, so they're
          // rendered fully bright rather than edge-graded — that contrast
          // against the textured shafts is what reads as "crossbar", not
          // just more vertical noise.
          let edge = false;
          if (upright) {
            const dist = halfWidth - Math.abs(Math.abs(u) - 0.5);
            edge = dist < 0.025 || v < 0.14 || v > 0.9;
          } else {
            edge = true;
          }

          const fillProb = edge ? 0.94 : 0.42;
          if (Math.random() > fillProb) continue;

          const isAccent = threshold || (edge && Math.random() < 0.12);
          const alpha = edge ? 0.85 : 0.5;
          ctx.fillStyle = `rgba(${isAccent ? accent : color},${alpha})`;
          const glyph = GATE_GLYPHS[(row * 31 + col * 17) % GATE_GLYPHS.length];
          ctx.fillText(glyph, col * cell, row * cell + cell / 2);
        }
      }
    };

    draw();
    window.addEventListener("resize", draw);
    return () => window.removeEventListener("resize", draw);
  }, []);

  return <canvas ref={canvasRef} aria-hidden className="h-full w-full" />;
}

// Camera-focus-style corner brackets (no numeric labels) sweeping slowly
// through the gate's aperture on a loop — "every transaction is being
// actively checked," rendered as inspection, not decoration.
function ScanBracket() {
  const corner =
    "absolute h-3.5 w-3.5 border-verdant-500/50 dark:border-verdant-400/50";
  return (
    <div
      aria-hidden
      className="gate-scan pointer-events-none absolute left-1/2 h-[22%] w-[42%] -translate-x-1/2"
    >
      <div className={`${corner} left-0 top-0 border-l border-t`} />
      <div className={`${corner} right-0 top-0 border-r border-t`} />
      <div className={`${corner} bottom-0 left-0 border-b border-l`} />
      <div className={`${corner} bottom-0 right-0 border-b border-r`} />
    </div>
  );
}

function GateBackdrop({ reduceMotion }: { reduceMotion: boolean }) {
  return (
    <motion.div
      aria-hidden
      initial={{ opacity: 0 }}
      animate={{
        opacity: 1,
        transition: reduceMotion
          ? { duration: 0 }
          : { duration: 1.1, ease: EASE_OUT, delay: 0.15 },
      }}
      className="hero-vignette pointer-events-none absolute inset-0 z-[1] flex items-center justify-center overflow-hidden"
    >
      <div className="relative h-full max-h-[420px] w-[min(55%,420px)] md:max-h-[560px] md:w-[min(48%,560px)] lg:max-h-[680px] lg:w-[min(42%,680px)] 2xl:max-h-[820px] 2xl:w-[min(40%,820px)]">
        <GateCanvas />
        <ScanBracket />
      </div>
    </motion.div>
  );
}

const heroStagger: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.1, delayChildren: 0.05 },
  },
};

const heroItem: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: EASE_OUT } },
};

function Annotation({
  label,
  className,
  lineClassName,
}: {
  label: string;
  className: string;
  lineClassName: string;
}) {
  return (
    <motion.div
      variants={heroItem}
      className={`pointer-events-none absolute hidden items-center gap-0 md:flex ${className}`}
    >
      <span className="whitespace-nowrap rounded-sm border border-border bg-surface-raised px-2.5 py-1 font-mono text-[11px] tracking-widest text-text-muted">
        {label}
      </span>
      <span className={`block bg-ink-400/60 ${lineClassName}`} />
    </motion.div>
  );
}

type DemoState = "idle" | "evaluating" | "blocked";

export default function Home() {
  const [demo, setDemo] = useState<DemoState>("idle");
  const reduceMotion = useReducedMotion();

  const runDemo = () => {
    if (demo !== "idle") return;
    setDemo("evaluating");
    setTimeout(() => setDemo("blocked"), 900);
  };

  const cardTransition = reduceMotion
    ? { duration: 0 }
    : { duration: 0.5, ease: EASE_OUT };

  return (
    <main className="relative flex flex-1 flex-col overflow-hidden">
      <TokenCanvas />

      <motion.section
        variants={heroStagger}
        initial="hidden"
        animate="show"
        className="relative z-10 mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center px-6 py-16 lg:max-w-6xl xl:max-w-7xl 2xl:max-w-[100rem]"
      >
        <motion.p
          variants={heroItem}
          className="font-mono text-xs tracking-[0.3em] text-text-muted"
        >
          MANDATECHECK
        </motion.p>
        <motion.h1
          variants={heroItem}
          className="mt-3 text-center text-3xl font-semibold text-text-primary lg:text-4xl xl:text-5xl 2xl:text-6xl"
        >
          A deterministic gate for AI-agent payments
        </motion.h1>

        {/* Fixed-height stage so the demo card never shifts layout. */}
        <div className="relative mt-10 flex min-h-[340px] w-full flex-col items-center md:min-h-[440px] lg:min-h-[520px] 2xl:min-h-[620px]">
          <GateBackdrop reduceMotion={!!reduceMotion} />

          {demo === "idle" && (
            <>
              <Annotation
                label="EVERY TRANSACTION CHECKED"
                className="left-[4%] top-[8%] flex-row"
                lineClassName="h-px w-16"
              />
              <Annotation
                label="ZERO LLM IN THE DECISION"
                className="right-[3%] top-[22%] flex-row-reverse"
                lineClassName="h-px w-16"
              />
              <Annotation
                label="BLOCKED IN REAL TIME"
                className="bottom-[6%] left-[8%] flex-row"
                lineClassName="h-px w-12"
              />
            </>
          )}

          <AnimatePresence mode="wait">
            {demo === "idle" && (
              <motion.button
                key="cta"
                variants={heroItem}
                initial="hidden"
                animate="show"
                exit={{ opacity: 0, transition: { duration: 0.2 } }}
                whileHover={
                  reduceMotion
                    ? undefined
                    : {
                        scale: 1.03,
                        transition: { type: "spring", stiffness: 300, damping: 20 },
                      }
                }
                onClick={runDemo}
                className="hero-pulse absolute left-1/2 top-1/2 z-20 -translate-x-1/2 -translate-y-1/2 rounded-full border border-verdant-500 bg-verdant-600 px-8 py-8 font-mono text-sm font-medium tracking-widest text-ink-50"
              >
                SEE IT LIVE
              </motion.button>
            )}

            {demo === "evaluating" && (
              <motion.div
                key="evaluating"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0, transition: cardTransition }}
                exit={{ opacity: 0, transition: { duration: 0.2 } }}
                className="relative z-20 mt-16 flex flex-col items-center gap-3 py-8"
              >
                <span className="font-mono text-xs tracking-widest text-text-muted">
                  EVALUATING txn_8842 AGAINST MANDATE mnd_2210…
                </span>
                <span className="h-1.5 w-1.5 animate-ping rounded-full bg-verdant-500" />
              </motion.div>
            )}

            {demo === "blocked" && (
              <motion.div
                key="blocked"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0, transition: cardTransition }}
                className="relative z-20 mt-10 w-full max-w-md rounded-lg border border-block-500 bg-surface-raised p-4"
              >
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
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <motion.h2
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.7, ease: EASE_OUT }}
          className="mt-12 text-center font-serif text-4xl leading-tight text-text-primary md:text-5xl xl:text-6xl"
        >
          The agent suggests.
          <br />
          The rules decide.
        </motion.h2>
      </motion.section>
    </main>
  );
}
