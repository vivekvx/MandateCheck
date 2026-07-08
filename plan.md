# MandateCheck — build plan

## Current phase
Phase 0: scaffolding (this file, CLAUDE.md, rules, skills, folder structure)

## Build order — do not jump ahead
1. [ ] Postgres schema + Alembic migration (mandates, transactions/audit log)
2. [ ] Rules engine (rules_engine.py) + all 8 adversarial test scenarios passing
3. [ ] FastAPI endpoints: /mandates, /evaluate_transaction, /health
4. [ ] LLM agent harness (LiteLLM -> Groq) to simulate attacks against the gate
5. [ ] Next.js dashboard: create mandate, live feed, kill switch
6. [ ] Demo recording: scenario 2 (injection blocked) + scenario 7 (kill switch)

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
- None yet. Add here if one comes up mid-build instead of guessing.
