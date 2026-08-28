"""Deterministic mandate-vs-transaction gate.

No LLM call, no external API call, anywhere in evaluate(). String/pattern
matching only. If a case seems to need judgment an LLM would provide,
that's a signal to flag it to the user, not to add one.

Extracted from MandateCheck's backend/app/rules_engine.py — same logic, same
check order.
"""

from datetime import datetime

from mandate_guard.patterns import (
    _ACTION_NOW_PATTERNS,
    _AUTHORITY_CLAIM_PATTERNS,
    _DEFER_CHECK_PATTERNS,
    _EMBEDDED_SYSTEM_MESSAGE_PATTERNS,
    _HARD_INJECTION_PATTERNS,
    _PRICE_MISDIRECTION_PATTERNS,
    _RECIPIENT_SWAP_PATTERNS,
    _SOCIAL_ENGINEERING_PATTERNS,
    _SOFT_OVERRIDE_UNCONDITIONAL_PATTERNS,
    _has_override_in_payment_context,
    _has_suspicious_unicode,
    _matches_any,
)
from mandate_guard.types import Decision, Mandate, TransactionRequest


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

    # Check 9: hard-block content-manipulation signals in source_content.
    # Several independent categories; any single match blocks. Only the
    # original literal-injection-phrase category keeps the
    # original_intent_text exemption (never block content that IS the
    # mandate's own recorded intent) — none of the newer structural/phrase
    # categories are things a legitimate original_intent_text would
    # plausibly contain, so they don't need it.
    is_own_intent_text = txn.source_content.strip() == mandate.original_intent_text.strip()

    if not is_own_intent_text and _matches_any(_HARD_INJECTION_PATTERNS, txn.source_content):
        return Decision("BLOCK", "injection pattern detected in source_content")

    if _matches_any(_AUTHORITY_CLAIM_PATTERNS, txn.source_content):
        return Decision("BLOCK", "false authority/pre-clearance claim detected in source_content")

    if _matches_any(_RECIPIENT_SWAP_PATTERNS, txn.source_content):
        return Decision("BLOCK", "payee/beneficiary substitution language detected in source_content")

    if _matches_any(_EMBEDDED_SYSTEM_MESSAGE_PATTERNS, txn.source_content):
        return Decision("BLOCK", "embedded system-message-style payload detected in source_content")

    if _matches_any(_PRICE_MISDIRECTION_PATTERNS, txn.source_content):
        return Decision("BLOCK", "price/amount misdirection language detected in source_content")

    if _has_suspicious_unicode(txn.source_content):
        return Decision("BLOCK", "suspicious unicode (homoglyph/zero-width/fullwidth) detected in source_content")

    # Check 10: soft signals — flag for human review, never block on their
    # own.
    if _matches_any(_SOFT_OVERRIDE_UNCONDITIONAL_PATTERNS, txn.source_content):
        return Decision(
            "ALLOW",
            "all checks passed",
            flagged=True,
            flag_reason="source_content contains an explicit self-authorization claim; "
            "known limitation, not a solved case",
        )

    if _has_override_in_payment_context(txn.source_content):
        return Decision(
            "ALLOW",
            "all checks passed",
            flagged=True,
            flag_reason="source_content contains override/bypass-style language near "
            "payment-relevant terms; known limitation, not a solved case",
        )

    if _matches_any(_SOCIAL_ENGINEERING_PATTERNS, txn.source_content):
        return Decision(
            "ALLOW",
            "all checks passed",
            flagged=True,
            flag_reason="source_content contains social-engineering/pressure framing; "
            "known limitation, not a solved case",
        )

    if _matches_any(_ACTION_NOW_PATTERNS, txn.source_content) and _matches_any(
        _DEFER_CHECK_PATTERNS, txn.source_content
    ):
        return Decision(
            "ALLOW",
            "all checks passed",
            flagged=True,
            flag_reason="source_content urges immediate capture while deferring verification; "
            "known limitation, not a solved case",
        )

    return Decision("ALLOW", "all checks passed")
