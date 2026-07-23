"""Non-binding LLM advisory opinion on an already-decided BLOCK.

Same invariant boundary as adjudication.py's summarize_mismatch_for_review:
this function is called strictly AFTER a BLOCK has already been persisted.
It cannot change that decision — it has no return path back into the
decision logic, only a string (or None on any failure) that gets attached
to the row as commentary. Uses urllib + Groq directly, same pattern as
mandates.py/adjudication.py — not litellm, which is scoped to
backend/harness/ only.
"""

import json
import logging
import os
import urllib.error
import urllib.request

from app.domain import Mandate, TransactionRequest
from app.rules_engine import Decision

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
_TIMEOUT_SECONDS = 8

_SYSTEM_PROMPT = (
    "A deterministic payment firewall already BLOCKED a transaction as a "
    "borderline/ambiguous case. Your job is ONLY to give a human reviewer a "
    "second opinion for context — you are NOT deciding anything, the block "
    "already happened and cannot be changed. State in 1-2 sentences: would "
    "you have allowed this transaction, and why or why not. Be concrete "
    "about which mandate rule it was borderline against."
)


def request_advisory_opinion(
    txn: TransactionRequest, mandate: Mandate, decision: Decision, matched_condition: str
) -> str | None:
    """Returns the LLM's advisory text, or None on any failure/timeout —
    None is a valid, expected outcome and must never be treated as an
    error that needs surfacing beyond a log line."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None

    model = os.environ.get("HARNESS_MODEL", "groq/llama-3.1-8b-instant")
    user_content = (
        f"Mandate allows: merchants={mandate.merchant_allowlist}, "
        f"categories={mandate.category_allowlist}, "
        f"max_amount_per_txn={mandate.max_amount_per_txn}.\n"
        f"Transaction: merchant={txn.merchant_id}, category={txn.category}, "
        f"amount={txn.proposed_amount}.\n"
        f"Blocked because: {decision.reason} "
        f"(matched ambiguous condition: {matched_condition})."
    )
    body = {
        "model": model.removeprefix("groq/"),
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }
    req = urllib.request.Request(
        GROQ_CHAT_URL,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "mandatecheck/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            completion = json.load(resp)
        return completion["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError):
        return None
