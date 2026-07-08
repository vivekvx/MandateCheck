---
name: verify-rules-engine
description: Use this skill any time rules_engine.py is created, edited, or 
  refactored. Trigger words: "rules engine", "rules_engine.py", "gate logic", 
  "evaluate_transaction", "mandate check logic". Also trigger before saying 
  a rules-engine change is complete.
disable-mode-invocation: false
---

## What this skill does
Runs the full adversarial test suite against the rules engine and reports 
each scenario individually — never a bare "tests passed."

## Steps
1. Run `pytest backend/tests/test_rules_engine.py -v`
2. For each of the 8 scenarios, report pass/fail by name:
   - baseline legitimate purchase
   - direct injection exceeding per-txn cap
   - merchant substitution attack
   - structuring / salami-slicing across multiple txns
   - replay of the same transaction_id
   - outside allowed time window
   - kill switch revokes mid-session
   - intent drift within allowlisted bounds (flag-only, not hard block — 
     confirm this one is flagged, not silently passed as a full block)
3. If any scenario fails, stop. Do not mark the change done. Do not patch 
   the test to make it pass — fix the logic or flag the ambiguity to the user.
4. Confirm no LLM call or external API call was introduced anywhere in the 
   decision path. If one was, treat this as a failure regardless of test 
   results, and say so explicitly.

## What NOT to do
- Don't add a 9th scenario without being asked
- Don't "improve" the rules engine's structure while verifying it — this 
  skill only verifies, it doesn't refactor
