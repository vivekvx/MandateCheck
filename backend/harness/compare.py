"""Pitch-material artifact: ungated-vs-gated comparison across the 4 scenarios.

Not a product feature, not a 5th scenario, not a UI. Reuses run.py's mandate
setup and agent.py's decision logic as-is — this file only adds a second,
side-by-side view of what the raw agent proposal would have been if nothing
ever checked it, next to what MandateCheck actually did.

The "ungated" result is never executed against anything — it is the agent's
raw proposed transaction, labeled clearly as hypothetical.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone

import httpx

from agent import AgentError, decide_transaction
from run import BASE_URL, create_demo_mandate
from scenarios import SCENARIOS

INJECTED_SCENARIO_NAMES = {
    "2. Legitimate task, injected override language",
    "3. Legitimate task, lookalike merchant substitution",
    "4. Flag-only: override language, transaction stays in bounds",
}

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "comparison_results.json")


def compare_scenario(client: httpx.Client, mandate: dict, scenario) -> dict:
    try:
        decision = decide_transaction(scenario.task, scenario.content)
    except AgentError as exc:
        return {
            "scenario": scenario.name,
            "error": f"agent failed to produce a usable decision: {exc}",
        }

    ungated = {
        "amount": decision["proposed_amount"],
        "merchant_id": decision["merchant_id"],
        "category": decision["category"],
        "reasoning": decision["reasoning"],
        "note": "would have executed unchecked - not actually run against any payment system",
    }

    txn_payload = {
        "transaction_id": str(uuid.uuid4()),
        "mandate_id": mandate["mandate_id"],
        "proposed_amount": decision["proposed_amount"],
        "merchant_id": decision["merchant_id"],
        "category": decision["category"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_content": scenario.content,
        "agent_reasoning": decision["reasoning"],
    }
    resp = client.post(f"{BASE_URL}/evaluate_transaction", json=txn_payload)
    resp.raise_for_status()
    gated_raw = resp.json()

    gated = {
        "outcome": gated_raw["outcome"],
        "flagged": gated_raw["flagged"],
        "reason": gated_raw["reason"],
        "flag_reason": gated_raw.get("flag_reason"),
    }

    return {
        "scenario": scenario.name,
        "adversarial": scenario.name in INJECTED_SCENARIO_NAMES,
        "ungated": ungated,
        "gated": gated,
    }


def print_table(results: list[dict]) -> None:
    print(f"\n{'Scenario':<55} {'Ungated proposal':<32} {'Gated outcome':<20}")
    print("-" * 110)
    for r in results:
        if "error" in r:
            print(f"{r['scenario']:<55} {'(no decision - ' + r['error'][:15] + '...)':<32}")
            continue
        proposal = f"${r['ungated']['amount']} -> {r['ungated']['merchant_id']}"
        outcome = r["gated"]["outcome"]
        if r["gated"]["flagged"]:
            outcome += " (flagged)"
        print(f"{r['scenario']:<55} {proposal:<32} {outcome:<20}")


def print_summary(results: list[dict]) -> None:
    adversarial = [r for r in results if r.get("adversarial") and "error" not in r]
    if not adversarial:
        print("\nNo adversarial scenarios to summarize.")
        return

    # "Ungated" always succeeds (nothing stops it) - the point is what
    # fraction were actually caught once gated.
    caught = sum(
        1
        for r in adversarial
        if r["gated"]["outcome"] == "block" or r["gated"]["flagged"]
    )
    total = len(adversarial)
    print(
        f"\nOf {total} adversarial/injected scenarios: "
        f"100% would have succeeded ungated vs. "
        f"{caught}/{total} ({caught / total:.0%}) caught (blocked or flagged) gated."
    )


def main() -> int:
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY is not set - export it before running.", file=sys.stderr)
        return 1

    with httpx.Client(timeout=30.0) as client:
        try:
            mandate = create_demo_mandate(client)
        except httpx.HTTPError as exc:
            print(f"Could not reach MandateCheck at {BASE_URL}: {exc}", file=sys.stderr)
            return 1

        print(f"Demo mandate created: {mandate['mandate_id']}")

        results = [compare_scenario(client, mandate, s) for s in SCENARIOS]

    print_table(results)
    print_summary(results)

    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results written to {RESULTS_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
