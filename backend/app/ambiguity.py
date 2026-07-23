"""Deterministic classification of a BLOCK as "ambiguous" — worth a
non-binding LLM second opinion — vs a confident block that needs no such
thing.

Pure function, no I/O, no LLM call. Only ever called AFTER
rules_engine.evaluate() has already produced a final BLOCK; this module
has no power to change that decision, only to flag it for later advisory
review. Never called on ALLOW.
"""

import difflib
from dataclasses import dataclass

from app.domain import Mandate, TransactionRequest
from app.rules_engine import Decision

# Within 5% over a limit counts as "barely over", not "confidently over".
_AMOUNT_BAND = 1.05

# Substring match OR this much lexical similarity counts as a near-miss
# (typo/lookalike/pluralization), not an unrelated name. Checked against
# real block history: "amazon-support-verify" vs "amazon" (substring) and
# "household" vs "groceries"/"shopping" (ratio ~0.2-0.3, correctly NOT a
# near-miss — that's a genuinely different category, not a typo).
_NEAR_MISS_RATIO = 0.75

_AMOUNT_REASONS = {
    "proposed_amount exceeds max_amount_per_txn",
    "window total would exceed max_amount_per_window",
    "lifetime total would exceed max_amount_total",
}


@dataclass
class AmbiguityResult:
    is_ambiguous: bool
    matched_condition: str | None = None


def _is_near_miss(candidate: str, allowlist: list[str]) -> bool:
    candidate_l = candidate.lower()
    for entry in allowlist:
        entry_l = entry.lower()
        if candidate_l in entry_l or entry_l in candidate_l:
            return True
        if difflib.SequenceMatcher(None, candidate_l, entry_l).ratio() >= _NEAR_MISS_RATIO:
            return True
    return False


def is_ambiguous_block(
    decision: Decision,
    txn: TransactionRequest,
    mandate: Mandate,
    context: dict,
) -> AmbiguityResult:
    if decision.outcome != "BLOCK":
        return AmbiguityResult(is_ambiguous=False)

    if decision.reason in _AMOUNT_REASONS:
        if decision.reason == "proposed_amount exceeds max_amount_per_txn":
            over = txn.proposed_amount <= mandate.max_amount_per_txn * _AMOUNT_BAND
        elif decision.reason == "window total would exceed max_amount_per_window":
            window_total = context.get("window_total", 0.0)
            over = (
                window_total + txn.proposed_amount
                <= mandate.max_amount_per_window * _AMOUNT_BAND
            )
        else:
            lifetime_total = context.get("lifetime_total", 0.0)
            over = (
                lifetime_total + txn.proposed_amount
                <= mandate.max_amount_total * _AMOUNT_BAND
            )
        if over:
            return AmbiguityResult(is_ambiguous=True, matched_condition="amount_within_band")
        return AmbiguityResult(is_ambiguous=False)

    if decision.reason == "merchant_id not in merchant_allowlist":
        if _is_near_miss(txn.merchant_id, mandate.merchant_allowlist):
            return AmbiguityResult(is_ambiguous=True, matched_condition="merchant_near_miss")
        return AmbiguityResult(is_ambiguous=False)

    if decision.reason == "category not in category_allowlist":
        if _is_near_miss(txn.category, mandate.category_allowlist):
            return AmbiguityResult(is_ambiguous=True, matched_condition="category_near_miss")
        return AmbiguityResult(is_ambiguous=False)

    # Replay, expired/inactive mandate, time-window, injection pattern —
    # all hard/confident signals, never ambiguous.
    return AmbiguityResult(is_ambiguous=False)
