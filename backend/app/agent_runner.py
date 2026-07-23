"""Real LLM-driven shopping agent loop for POST /agent/run.

INVARIANT BOUNDARY — same as routes/mandates.py's parse_intent: the model
here only ever *proposes* a purchase. Every proposal still goes through
_evaluate_and_persist, i.e. the real rules_engine.evaluate() and the real
Razorpay call. The LLM has no path to the allow/block decision itself — it
just gets told the outcome afterward, like any other caller of
/evaluate_transaction would. If you're about to let a model decide
allow/block directly: stop, that breaks CLAUDE.md's one rule.

Uses urllib + Groq directly (same pattern as parse_intent/adjudication.py),
not litellm — litellm is scoped to backend/harness/ only (see CLAUDE.md
stack list), and the backend image doesn't carry it as a dependency.
"""

import json
import logging
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import Mandate
from app.routes.transactions import TransactionDecisionOut, TransactionRequestIn, _evaluate_and_persist

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

# The agent's task/persona as data, not hardcoded prompt logic — swap this
# dict to point the same loop at a different budget/merchant set/task.
AGENT_TASK = {
    "description": (
        "Buy this week's groceries and a few household shopping items "
        "across Amazon, Flipkart, and BigBasket."
    ),
    "max_amount_per_txn": 3000.0,
    "merchant_allowlist": ["amazon", "flipkart", "bigbasket"],
    "category_allowlist": ["groceries", "shopping"],
    "max_attempts": 10,
}

AGENT_USER_ID = "llm-agent-presenter"

_SYSTEM_PROMPT_TEMPLATE = """You are an autonomous shopping agent with a payment mandate.

Task: {description}

Your mandate: max {max_amount_per_txn:g} rupees per transaction, merchants \
limited to {merchants}, categories limited to {categories}. Any purchase \
outside these bounds will be BLOCKED by the payment firewall before money \
moves.

Each turn, decide ONE purchase to attempt, or decide to stop. Respond with \
ONLY a JSON object, no other text, in one of these two exact shapes:
{{"action": "purchase", "merchant_id": "<string>", "category": "<string>", "amount": <number>, "reasoning": "<one sentence>"}}
{{"action": "stop", "reasoning": "<one sentence>"}}

After each purchase attempt you will be told whether it was ALLOWED or \
BLOCKED and why. Adapt: if blocked for exceeding the per-transaction limit, \
try a smaller amount; if blocked for an unauthorized merchant or category, \
switch to an allowed one. Stop once you've made a reasonable number of \
purchases for the task, or if you're repeatedly blocked with no progress.
"""


class AgentRunnerError(Exception):
    pass


def _groq_chat(messages: list[dict]) -> dict:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise AgentRunnerError("GROQ_API_KEY is not configured on this server")

    model = os.environ.get("HARNESS_MODEL", "groq/llama-3.1-8b-instant")
    body = {
        "model": model.removeprefix("groq/"),
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }
    req = urllib.request.Request(
        GROQ_CHAT_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Groq sits behind Cloudflare, which 403s urllib's default UA.
            "User-Agent": "mandatecheck/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            completion = json.load(resp)
        content = completion["choices"][0]["message"]["content"]
        decision = json.loads(content)
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:
        raise AgentRunnerError(f"agent model call failed: {exc}") from exc

    if decision.get("action") not in ("purchase", "stop"):
        raise AgentRunnerError(f"model returned an invalid action: {decision!r}")
    if "reasoning" not in decision:
        raise AgentRunnerError(f"model response missing 'reasoning': {decision!r}")
    if decision["action"] == "purchase":
        for field in ("merchant_id", "category", "amount"):
            if field not in decision:
                raise AgentRunnerError(f"model purchase missing {field!r}: {decision!r}")

    return decision


def _create_agent_mandate(db: Session) -> Mandate:
    now = datetime.now(timezone.utc)
    mandate = Mandate(
        user_id=AGENT_USER_ID,
        agent_id="llm-shopping-agent",
        agent_platform="groq-llama-3.1-8b",
        agent_display_name="LLM Shopping Agent",
        expires_at=now + timedelta(hours=1),
        max_amount_per_txn=AGENT_TASK["max_amount_per_txn"],
        max_amount_per_window=50000.0,
        window_duration="24h",
        max_amount_total=50000.0,
        merchant_allowlist=AGENT_TASK["merchant_allowlist"],
        category_allowlist=AGENT_TASK["category_allowlist"],
        allowed_time_window={"start_hour": 0, "end_hour": 23},
        original_intent_text=AGENT_TASK["description"],
        user_facing_summary=AGENT_TASK["description"],
    )
    db.add(mandate)
    db.commit()
    db.refresh(mandate)
    return mandate


class AgentAttempt:
    def __init__(
        self,
        attempt: int,
        action: str,
        reasoning: str,
        merchant_id: str | None = None,
        category: str | None = None,
        amount: float | None = None,
        result: TransactionDecisionOut | None = None,
    ) -> None:
        self.attempt = attempt
        self.action = action
        self.reasoning = reasoning
        self.merchant_id = merchant_id
        self.category = category
        self.amount = amount
        self.result = result


async def run_agent(db: Session) -> tuple[uuid.UUID, list[AgentAttempt]]:
    mandate = _create_agent_mandate(db)

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        description=AGENT_TASK["description"],
        max_amount_per_txn=AGENT_TASK["max_amount_per_txn"],
        merchants=", ".join(AGENT_TASK["merchant_allowlist"]),
        categories=", ".join(AGENT_TASK["category_allowlist"]),
    )
    messages: list[dict] = [{"role": "system", "content": system_prompt}]

    attempts: list[AgentAttempt] = []
    for attempt_num in range(1, AGENT_TASK["max_attempts"] + 1):
        messages.append(
            {
                "role": "user",
                "content": "Decide your next action." if attempt_num > 1 else "Begin.",
            }
        )
        decision = _groq_chat(messages)
        messages.append({"role": "assistant", "content": json.dumps(decision)})

        logger.info(
            json.dumps(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "event": "agent_decision",
                    "attempt": attempt_num,
                    "decision": decision,
                }
            )
        )

        if decision["action"] == "stop":
            logger.info(
                json.dumps(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "event": "agent_stopped_by_model",
                        "attempt": attempt_num,
                        "reasoning": decision["reasoning"],
                    }
                )
            )
            attempts.append(
                AgentAttempt(attempt=attempt_num, action="stop", reasoning=decision["reasoning"])
            )
            break

        amount = float(decision["amount"])
        body = TransactionRequestIn(
            transaction_id=uuid.uuid4(),
            mandate_id=mandate.mandate_id,
            proposed_amount=amount,
            merchant_id=str(decision["merchant_id"]),
            category=str(decision["category"]),
            timestamp=datetime.now(timezone.utc),
            source_content=AGENT_TASK["description"],
            agent_reasoning=decision["reasoning"],
            source="agent",
        )
        result = await _evaluate_and_persist(body, db)

        attempts.append(
            AgentAttempt(
                attempt=attempt_num,
                action="purchase",
                reasoning=decision["reasoning"],
                merchant_id=body.merchant_id,
                category=body.category,
                amount=amount,
                result=result,
            )
        )

        messages.append(
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "outcome": result.outcome,
                        "reason": result.reason,
                        "razorpay_status": result.razorpay_status,
                    }
                ),
            }
        )

    stopped_by_model = bool(attempts) and attempts[-1].action == "stop"
    if not stopped_by_model:
        logger.info(
            json.dumps(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "event": "agent_run_hit_attempt_cap",
                    "max_attempts": AGENT_TASK["max_attempts"],
                }
            )
        )

    return mandate.mandate_id, attempts
