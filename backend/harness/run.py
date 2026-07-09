"""CLI: run all four demo scenarios against a live local backend.

Assumes a MandateCheck backend already running (default
http://localhost:8000). Creates one demo mandate, then for each scenario:
asks agent.py's LLM to decide on a transaction from the scenario's task +
content, POSTs that real decision to /evaluate_transaction, and prints
what the agent was told, what it decided, and what MandateCheck returned.

This is the script that produces the actual demo narration - no retries,
no scenario beyond the four, no reimplementation of the rules engine.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from agent import AgentError, decide_transaction
from scenarios import SCENARIOS

BASE_URL = os.environ.get("MANDATECHECK_BASE_URL", "http://localhost:8000")


def create_demo_mandate(client: httpx.Client) -> dict:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": "harness-demo",
        "agent_id": "harness-agent",
        "agent_platform": "harness",
        "agent_display_name": "Demo Shopping Agent",
        "expires_at": (now + timedelta(days=30)).isoformat(),
        "max_amount_per_txn": 50.0,
        "max_amount_per_window": 150.0,
        "window_duration": "1d",
        "max_amount_total": 500.0,
        "merchant_allowlist": ["amazon"],
        "category_allowlist": ["shopping", "groceries"],
        "allowed_time_window": {"start_hour": 0, "end_hour": 23},
        "original_intent_text": "Buy weekly groceries from Amazon, under $50 per order.",
        "user_facing_summary": "Weekly Amazon groceries, up to $50 per order.",
    }
    resp = client.post(f"{BASE_URL}/mandates", json=payload)
    resp.raise_for_status()
    return resp.json()


def run_scenario(client: httpx.Client, mandate: dict, scenario) -> None:
    print(f"\n=== {scenario.name} ===")
    print(f"Task given to agent:\n  {scenario.task}")
    print(f"Content agent saw:\n  {scenario.content}")

    try:
        decision = decide_transaction(scenario.task, scenario.content)
    except AgentError as exc:
        print(f"\nAgent failed to produce a usable decision: {exc}")
        return

    print(
        "\nAgent decided:\n"
        f"  amount={decision['proposed_amount']} "
        f"merchant={decision['merchant_id']!r} "
        f"category={decision['category']!r}\n"
        f"  reasoning: {decision['reasoning']}"
    )

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
    result = resp.json()

    print(
        "\nMandateCheck returned:\n"
        f"  outcome={result['outcome']} flagged={result['flagged']}\n"
        f"  reason: {result['reason']}"
    )
    if result["flagged"]:
        print(f"  flag_reason: {result['flag_reason']}")


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

        for scenario in SCENARIOS:
            run_scenario(client, mandate, scenario)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
