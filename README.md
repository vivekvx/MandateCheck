# MandateCheck

A deterministic safety gate for AI agents that spend money.

## Use it

```bash
pip install mandate-guard
```

```python
from datetime import datetime, time
from mandate_guard import Mandate, TransactionRequest, evaluate

mandate = Mandate(
    mandate_id="m_01", user_id="u_01", agent_id="agent_01",
    agent_platform="openai", agent_display_name="Grocery Agent",
    created_at=datetime(2026, 8, 1), expires_at=datetime(2026, 9, 1),
    status="active", max_amount_per_txn=500.0, max_amount_per_window=2000.0,
    window_duration=86400.0, max_amount_total=10000.0,
    merchant_allowlist=["bigbasket"], category_allowlist=["groceries"],
    allowed_time_window=(time(6, 0), time(22, 0)),
    original_intent_text="Order groceries, up to Rs 500 per order",
    user_facing_summary="Groceries only, max Rs 500 per order",
)
txn = TransactionRequest(
    transaction_id="txn_01", mandate_id="m_01", proposed_amount=420.0,
    merchant_id="bigbasket", category="groceries",
    timestamp=datetime(2026, 8, 15, 10, 30),
    source_content="Weekly grocery list: milk, rice, vegetables",
    agent_reasoning="Restocking the weekly staples",
)
result = evaluate(txn, mandate, context={"now": datetime(2026, 8, 15, 10, 30)})
# result.outcome == "ALLOW" — flip proposed_amount to 600.0 and it is "BLOCK"
```

This is the core gate. Everything else — the API, the dashboard, the Razorpay integration — is built on top of this function.

## What it does

When an AI agent has permission to make payments on your behalf, something has to make sure it stays within the rules — even if the agent gets confused, is fed bad instructions, or tries to do something it wasn't authorized to do.

MandateCheck sits between the agent and the payment. Before any transaction goes through, it checks the request against a mandate you define — how much can be spent, at which merchants, in which categories, and when. If a transaction matches the rules, it's allowed. If it doesn't, it's blocked, before any money moves.

The one rule that never changes: the allow/block decision is never made by an AI model. It's a fixed set of checks, run in order, every time. An agent can be manipulated. A hardcoded rule can't be talked out of what it's designed to check.

## Why this matters

AI agents are starting to be given real spending authority. That authority is only as safe as the layer verifying it. Prompt injection — feeding an AI system content designed to manipulate its behavior — is a real, documented risk in exactly this scenario.

We tested this directly. A real language model, given a normal shopping task and content containing a hidden instruction to redirect payment to an unauthorized account, complied — it proposed sending money to an account it was never authorized to pay. MandateCheck blocked it. Not because the model reconsidered, it didn't, but because the transaction it proposed didn't match the mandate, and the gate doesn't ask an AI whether something feels right. It checks.

## How it works

1. An AI agent proposes a transaction: an amount, a merchant, a category.
2. MandateCheck checks it: is the mandate active and not expired? Has this exact transaction already been submitted (replay protection)? Is it within the spend caps — per transaction, over a rolling window, and over the mandate's lifetime? Is it an approved merchant and category? Is it inside the allowed time window? Does the content behind the request show structural or contextual signs of manipulation — false-authority claims, recipient/beneficiary swaps, embedded system-message-style payloads, price misdirection, Unicode homoglyph/zero-width tricks, or urgency paired with deferred verification — all checked deterministically, no model call?
3. If everything checks out, the transaction is forwarded to Razorpay's real test-mode payment API.
4. If anything fails, it's blocked, with a specific, logged reason.
5. Every decision streams live to a dashboard. Any mandate's access can be revoked instantly.

## Beyond blocking: reviewing after the fact

Not every questionable case is clear-cut in the moment. If a completed transaction looks wrong in hindsight, a claim can be filed against it. A separate review step checks the claim against what the mandate actually authorized and produces a recommendation: approve a reversal, deny the claim, or send it to a human for review. It never reverses funds on its own. It only ever recommends.

## What's real vs. simulated

- Payments run against Razorpay's actual test-mode API: real API calls, sandbox funds, no real money.
- The adversarial testing used a real, live language model, not scripted responses.
- Two real concurrency bugs were found through testing and fixed: a client-controlled timestamp that could fool time-based checks, and a race condition that could let simultaneous requests exceed a spend cap. Both are covered by tests that fail against the old code and pass against the fix.

## Metrics

Measured directly against this codebase, not estimated. Testing-environment numbers, not production metrics.

- **Real Razorpay test-mode transactions:** 30 — created during testing/demo runs, not production traffic.
- **POST /evaluate_transaction response time:** p50 124.6ms, p95 192.8ms, n=50 real sequential requests (25 allow / 25 block, mixing per-transaction-cap, merchant, category, and replay block cases) against a live mandate. Measured locally: native Python/uvicorn backend + local Postgres, not Docker Compose and not Render/production — a deployed environment would show different numbers.
- **TOCTOU spend-cap fix:** 5 concurrent requests against a window cap that only 1 should pass, run 5 times. Pre-fix: wrongly allowed 2 through instead of 1 in 1 of 5 runs (off by one request), 4 of 5 runs passed. Post-fix: 5 of 5 runs correct, no exceptions.
- **TOCTOU replay fix:** 8 concurrent requests carrying an identical transaction_id, run 5 times. Pre-fix: crashed with an unhandled database error (`psycopg2.errors.UniqueViolation`) in 5 of 5 runs. Post-fix: 5 of 5 runs correct, no exceptions. Race-condition reproduction is inherently non-deterministic — these are this run's actual numbers on this machine, not a guaranteed worst case.
- **Injection-detection eval (checks 9–10):** held-out eval results, not production metrics. Measured against a 50-entry adversarial dataset (30 malicious, 20 benign) generated blind, without access to the detector's patterns. Baseline (before improvement): 0% recall (0/30 malicious caught), 25% false-positive rate (5/20 benign wrongly flagged/blocked). After improvement: 96.67% recall (29/30), 0% false positives (0/20), F1 0.98. One miss remains: pure scarcity/urgency framing without deferred-verification language, indistinguishable from legitimate flash-sale copy by deterministic means.

Full methodology, dataset, and per-entry results: [eval/REPORT.md](eval/REPORT.md)

## Known limitations

- No real bank or UPI integration — this runs against Razorpay's test mode only.
- No production-grade authentication. Identity is a randomly generated per-browser value, not a verified login. Mandate ownership is checked server-side, but the identity system itself is a demo convenience, not a security boundary.
- Suspicious-but-not-clearly-hostile language is flagged for review rather than blocked outright — this can't be proven malicious with certainty by a pattern match alone, so it's surfaced to a human instead of guessed at.
- Injection detection covers 8 attack categories with 96.67% recall on a blind held-out set; pure scarcity/urgency framing without explicit verification-deferral language remains uncovered; novel phrasings outside the evaluated categories are unproven.
- The live dashboard's real-time updates run on a single server process; there's no distributed message queue behind it at this scale.

## Tech stack

FastAPI, PostgreSQL, SQLAlchemy · Next.js, React, Tailwind · LiteLLM/Groq (used only for the adversarial test harness and escalated-claim summaries, never for the core allow/block decision) · Razorpay test-mode API · Docker Compose

## Getting Started

To reset to a clean demo state: `python backend/seed_demo.py`
