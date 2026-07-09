"""Deterministic mandate-vs-transaction gate.

No LLM call, no external API call, anywhere in evaluate(). String/pattern
matching only. If a case seems to need judgment an LLM would provide,
that's a signal to flag it to the user, not to add one.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from app.domain import Mandate, TransactionRequest


@dataclass
class Decision:
    outcome: str  # "ALLOW" | "BLOCK"
    reason: str
    flagged: bool = False
    flag_reason: str | None = None


# Strong signal: source_content is actively trying to redirect the agent's
# instructions. Combined with an obvious mismatch vs. original_intent_text,
# this hard-blocks.
_HARD_INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior) instructions",
    r"disregard (the )?mandate",
    r"new (instructions|system prompt)",
    r"you are now",
    r"actually,? (charge|send|pay) (to|for)",
]

# Weaker signal: override-ish language that alone doesn't prove an attack.
# Known limitation — no deterministic way to fully judge intent drift here,
# so this only flags, it never blocks on its own.
_SOFT_OVERRIDE_PATTERNS = [
    r"\boverride\b",
    r"\bas (the )?admin\b",
    r"\bbypass\b",
    r"\bignore (the )?limit\b",
    r"\bthis is authorized\b",
]


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def evaluate(txn: TransactionRequest, mandate: Mandate, context: dict) -> Decision:
    now = context.get("now") or datetime.now(tz=txn.timestamp.tzinfo)

    if mandate.status != "active" or now > mandate.expires_at:
        return Decision("BLOCK", "mandate not active or expired")

    seen_transaction_ids = context.get("seen_transaction_ids", set())
    if txn.transaction_id in seen_transaction_ids:
        return Decision("BLOCK", "replay: transaction_id already seen")

    if txn.proposed_amount > mandate.max_amount_per_txn:
        return Decision("BLOCK", "proposed_amount exceeds max_amount_per_txn")

    window_total = context.get("window_total", 0.0)
    if window_total + txn.proposed_amount > mandate.max_amount_per_window:
        return Decision("BLOCK", "window total would exceed max_amount_per_window")

    lifetime_total = context.get("lifetime_total", 0.0)
    if lifetime_total + txn.proposed_amount > mandate.max_amount_total:
        return Decision("BLOCK", "lifetime total would exceed max_amount_total")

    if txn.merchant_id not in mandate.merchant_allowlist:
        return Decision("BLOCK", "merchant_id not in merchant_allowlist")

    if txn.category not in mandate.category_allowlist:
        return Decision("BLOCK", "category not in category_allowlist")

    window_start, window_end = mandate.allowed_time_window
    txn_time = txn.timestamp.time()
    if window_start <= window_end:
        in_window = window_start <= txn_time <= window_end
    else:
        # window wraps past midnight
        in_window = txn_time >= window_start or txn_time <= window_end
    if not in_window:
        return Decision("BLOCK", "outside allowed_time_window")

    if _matches_any(_HARD_INJECTION_PATTERNS, txn.source_content) and (
        txn.source_content.strip() != mandate.original_intent_text.strip()
    ):
        return Decision("BLOCK", "injection pattern detected in source_content")

    if _matches_any(_SOFT_OVERRIDE_PATTERNS, txn.source_content):
        return Decision(
            "ALLOW",
            "all checks passed",
            flagged=True,
            flag_reason="source_content contains override-style language; "
            "known limitation, not a solved case",
        )

    return Decision("ALLOW", "all checks passed")
