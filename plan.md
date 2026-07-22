# MandateCheck — build plan

## Current phase
Phase 5: polish + demo (final phase)

## Build order — do not jump ahead
1-4. [x] done
5. [x] Run harness against real Groq output — done 2026-07-18, all 4
   scenarios live, transcript in backend/harness/demo-run-output.md
6. [x] Impeccable design QA pass — 9 issues found and fixed, verified
   clean build
7. [x] Demo recording — done 2026-07-18 against the live deployment:
   docs/demo-recording.gif (mandate created via UI, blocked + allowed
   transactions rendering in the live feed in real time)

## Decisions already made — do not revisit without explicit discussion
- Name: MandateCheck
- Rules engine is 100% deterministic, no LLM in that decision path — final
- Stack: FastAPI/Postgres backend, Next.js frontend, Groq for the agent harness only
- No real bank/UPI integration — simulated rail only
- Scope boundaries as listed in CLAUDE.md — final for this build

## Deferred, not forgotten — do not build until phase 1-6 are done
- Rust port of the rules engine (stretch goal only)
- Hash-chained audit log for tamper-evidence
- Multi-platform mandate aggregation (ChatGPT + Claude + Gullak in one view)

## New item (not one of the original 5 phases) — post-hoc claim adjudication
Deliberately scoped work beyond the original build, not a pivot on scope.
Added 2026-07-21.

- Purpose: after a transaction has already executed, a person/agent can file
  a claim disputing it; this layer triages the claim into
  auto_approved / auto_denied / escalated.
- The rule that must never be broken here, same weight as "no LLM in the
  rules engine": this layer NEVER executes a reversal or moves money. It
  only ever outputs a recommendation object, clearly labeled as a
  recommendation. Real fund reversal goes through bank/network dispute
  infrastructure this project has no access to and must not pretend to have.
- Deterministic triage only (adjudicate() in adjudication.py) — no LLM in
  steps that decide auto_approved/auto_denied/escalated. A case needing
  model judgment to pick a category belongs in escalated, full stop.
- Optional, bounded: for escalated claims only, an LLM may generate a
  plain-language mismatch SUMMARY for a human reviewer — never an
  approve/deny recommendation, and its output field is named distinctly so
  it can't be confused with the deterministic recommendation.
- Files owned by this item: backend/app/domain.py (new dataclasses only),
  backend/app/adjudication.py (new), backend/app/models.py (new Claim table
  only), backend/app/routes/claims.py (new), backend/alembic/ (new
  migration, Claim table only), backend/tests/test_adjudication.py (new).
  Does not touch rules_engine.py, existing domain.py dataclasses, Mandate
  or TransactionLog tables.
- No frontend, no auth, no webhook notifications for this item yet.

## Open questions — flag, don't silently decide
- Frontend host port is 7009, not 3000/4000 (both collided locally) —
  confirmed in docker-compose.yml and README, NEXT_PUBLIC_API_BASE_URL
  unaffected (still points at backend's 8000)
- No auth anywhere in the app; KillSwitch scoped to NEXT_PUBLIC_DEMO_USER_ID
  — deliberate, fine for demo, not a real multi-user boundary
