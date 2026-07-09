# MandateCheck — build plan

## Current phase
Phase 5: polish + demo (final phase)

## Build order — do not jump ahead
1-4. [x] done
5. [ ] Run harness against real Groq output (manual step — needs a real
   GROQ_API_KEY, see below)
6. [x] Impeccable design QA pass — 9 issues found and fixed, verified
   clean build
7. [ ] Demo recording: scenario 2 (injection blocked) + scenario 7
   (kill switch), using real harness output where possible

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

## Open questions — flag, don't silently decide
- Frontend host port is 4000, not 3000/7000 (both collided locally) —
  confirmed in docker-compose.yml and README, NEXT_PUBLIC_API_BASE_URL
  unaffected (still points at backend's 8000)
- No auth anywhere in the app; KillSwitch scoped to NEXT_PUBLIC_DEMO_USER_ID
  — deliberate, fine for demo, not a real multi-user boundary
