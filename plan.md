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

## Post-hoc fix — server-authoritative clock + atomic spend-cap/replay
Found by manual code review, not a pivot on scope. Added 2026-07-28.

Two correctness/security bugs in routes/transactions.py, both undermining
claims already made elsewhere (README's "fails closed", the replay-detection
scenario in rules_engine.py):

- **Client-controlled clock.** `context["now"]` (and the domain
  TransactionRequest's `.timestamp`, which rules_engine.py reads directly
  for the time-of-day window check) was built from the request body's own
  `timestamp` field — an agent could simply lie about the time to dodge
  expiry/time-window checks. Fixed: both now come from the server's own
  `datetime.now(timezone.utc)`. The client-claimed value is kept only as an
  audit field in structured logs (`claimed_timestamp`), never fed into any
  check.
- **TOCTOU races on spend caps and replay.** window/lifetime totals were a
  plain SELECT-then-INSERT with no lock — concurrent requests against the
  same mandate could all read the same pre-spend total and all pass a cap
  only one should fit under. Replay detection was a pre-check SELECT with
  the same flaw — two requests with the same transaction_id could both see
  "not seen yet." Fixed: a `SELECT ... FOR UPDATE` row lock on the mandate
  serializes concurrent evaluations per mandate (closes the cap race); an
  INSERT-attempt-first with the unique-constraint violation on
  transaction_id as the authoritative replay signal replaces the pre-check
  SELECT (closes the replay race), and happens before any Razorpay call so
  a replay can never create a duplicate order.
- No new locking/queueing infrastructure — Postgres row locks and the
  existing PK unique constraint only, proportional to the current
  single-instance scope.
- New tests: `backend/tests/test_concurrency.py` — fires genuinely
  concurrent requests (separate OS threads, separate DB sessions, separate
  event loops, bypassing TestClient's shared portal on purpose) directly
  against real Postgres. Confirmed both fail against the pre-fix code
  (2-4 of 5 wrongly allowed past a window cap; a replay run crashed with a
  real `UniqueViolation`) and pass reliably post-fix.
- Files touched: `backend/app/routes/transactions.py`,
  `backend/tests/test_concurrency.py` (new), plus a two-method mock
  passthrough (`with_for_update`, `flush`) added to the pre-existing
  `FakeSession`/`FakeQuery` test doubles in `test_advisory_triage.py` and
  `test_razorpay_integration.py` so they still model the new DB calls —
  nothing else in those two files changed. rules_engine.py itself was not
  touched.

## Open questions — flag, don't silently decide
- Frontend host port is 7009, not 3000/4000 (both collided locally) —
  confirmed in docker-compose.yml and README, NEXT_PUBLIC_API_BASE_URL
  unaffected (still points at backend's 8000)
- No auth anywhere in the app; KillSwitch scoped to NEXT_PUBLIC_DEMO_USER_ID
  — deliberate, fine for demo, not a real multi-user boundary
