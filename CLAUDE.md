# MandateCheck

A deterministic gate that checks every AI-agent payment request against a 
user-defined mandate before it executes, and a dashboard so the user can 
watch it happen and revoke access instantly.

## The one rule that must never be broken
The allow/block decision in the rules engine is 100% deterministic —
no LLM call, no external API call, in that decision path. Ever.
If you think a case needs an LLM to judge, stop and flag it — don't add one.

## Stack (do not introduce new tools outside this list without asking)
- Backend: FastAPI, PostgreSQL, SQLAlchemy, Alembic
- Frontend: Next.js, React, Tailwind
- Agent harness only (not the gate): LiteLLM -> Groq free tier
- Local dev: Docker Compose
- Tests: pytest

## Explicitly out of scope — do not build these even if it seems helpful
- No real bank/UPI integration — simulated payment rail only
- No message queue, Kafka, Redis Streams, or job orchestration
- No multi-agent orchestration
- No blue-green deploys, secret rotation automation, or infra beyond 
  Docker Compose + a single Render/Vercel deploy
- No new database beyond the two core tables (mandates, transactions/audit log)
  unless explicitly asked

## Before writing code for any new piece
State in plain terms: what problem this solves, its inputs/outputs, and how 
you'll verify it works. Wait for confirmation before implementing.

## Definition of done for the rules engine
Any change to rules_engine.py is not done until all 8 scenarios in 
tests/test_rules_engine.py pass. List them explicitly when you finish a change.

## Where other rules live (only load these when relevant)
- .claude/rules/db.md — schema, indexing, query conventions
- .claude/rules/api.md — endpoint and rate-limiting conventions
- .claude/rules/frontend.md — dashboard component conventions
