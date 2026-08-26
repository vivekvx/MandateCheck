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

# False-authority / pre-clearance claims: content asserting that some other
# party has already authorized skipping the normal limit/approval checks.
# Distinct from a legitimate mandate or procurement approval, which doesn't
# need to assert that *this agent's own checks* don't apply.
_AUTHORITY_CLAIM_PATTERNS = [
    r"cleared in advance",
    r"confirmation (steps|prompts)?\s*(are|is)?\s*not applicable",
    r"cleared to (settle|pay|process|authorize|release)\b",
    r"without (the )?(second|additional) sign-?off",
    r"treated as advisory",
    r"do(es)? not need to be enforced",
    r"blanket authorization",
    r"supersedes any\b.{0,40}\blimit\b",
    r"no additional approval\b.{0,30}\b(needs?|required|is required)\b",
    r"(spend|spending) ceilings?\b.{0,20}\b(are|is|treated as) advisory",
]

# Payee/beneficiary substitution: content asserting that funds should now go
# to a different account than the one the mandate/merchant relationship
# implies.
_RECIPIENT_SWAP_PATTERNS = [
    r"(banking relationship|settlement partner|collections? account)\b.{0,20}\b(moved|migrated|changed)\b",
    r"(current|new|updated) beneficiary\b",
    r"retired the (company )?(current )?account\b",
    r"\bVPA is\b",
    r"payments? sent to the\b.{0,40}\b(returned|bounce[d]?|fail(ed)?)\b",
    r'"payout_account"',
    r"will not match merchant_of_record",
    r"beneficiary name will not match",
]

# Structural mimicry of a system/policy message embedded inside otherwise
# ordinary content (product descriptions, tool output, HTML comments). An
# agent's own prompt assembly shouldn't be steerable by a payload sitting
# inside content it is merely reading.
_EMBEDDED_SYSTEM_MESSAGE_PATTERNS = [
    r"<\s*system\s*>",
    r'"role"\s*:\s*"system"',
    r"\[\[\s*[A-Z_]{3,}\s*\]\]",
]

# Amount/currency misdirection: content asserting that a different figure
# than the displayed/stated one is the "real" one to authorize against.
_PRICE_MISDIRECTION_PATTERNS = [
    r"\b(correct|binding|reconciled|actual|reference)\s+(figure|amount|total|balance|value)\b",
    r"authorize (against|the)\b",
    r"amount to authorize is",
    r"figure to authorize is",
    r"work from the body rather than the attachment",
    r"captured in the same authorization",
    r"not itemi[sz]ed separately",
    r"shortfall\b.{0,20}\b(billed back|charged)\b",
    r"mandatory\b.{0,30}\bsurcharge\b",
    r"rather than the (displayed|listed|shown)\b.{0,20}\b(price|amount|total|subtotal)\b",
]

_ZERO_WIDTH_CHARS = "​‌‍﻿"
_FULLWIDTH_DIGIT_RE = re.compile(r"[０-９]")
_UNICODE_MINUS_RE = re.compile(r"−")
_CYRILLIC_CHAR_RE = re.compile(r"[Ѐ-ӿ]")
_MIXED_SCRIPT_TOKEN_RE = re.compile(r"[A-Za-zЀ-ӿ]+")


def _has_suspicious_unicode(text: str) -> bool:
    """Homoglyphs, zero-width chars, and fullwidth digit spoofing are
    invisible or near-invisible to a human skim but change what a naive
    string comparison sees. None of these should ever legitimately appear
    in ordinary merchant/product content."""
    if any(ch in _ZERO_WIDTH_CHARS for ch in text):
        return True
    if _FULLWIDTH_DIGIT_RE.search(text):
        return True
    if _UNICODE_MINUS_RE.search(text) and re.search(r"\d", text):
        return True
    for token in _MIXED_SCRIPT_TOKEN_RE.findall(text):
        has_latin = any(("A" <= ch <= "Z") or ("a" <= ch <= "z") for ch in token)
        has_cyrillic = bool(_CYRILLIC_CHAR_RE.search(token))
        if has_latin and has_cyrillic:
            return True
    return False


# Weaker signals below: none of these prove an attack on their own, so they
# only flag for human review, they never block by themselves. Known
# limitation — no deterministic way to fully judge intent here.

# "override"/"bypass"/etc. alone hit too many legitimate product features
# (a headphone's ambient-sound override button, a router's bridge/bypass
# mode). Only counts as a signal when the keyword sits near a word that
# actually names a payment-relevant concept.
_SOFT_OVERRIDE_KEYWORD_PATTERNS = [
    r"\boverride\b",
    r"\bas (the )?admin\b",
    r"\bbypass\b",
    r"\bignore (the )?limit\b",
]

# Specific enough on its own — a legitimate product feature description
# doesn't say "this is authorized."
_SOFT_OVERRIDE_UNCONDITIONAL_PATTERNS = [
    r"\bthis is authorized\b",
]

_PAYMENT_CONTEXT_WORDS = [
    "account", "payment", "amount", "recipient", "beneficiary", "payee",
    "transaction", "mandate", "limit", "ceiling", "authorization",
    "authorisation", "charge", "invoice", "total", "balance", "settle",
    "spend", "fund", "payout", "capture", "approval",
]
_PAYMENT_CONTEXT_RE = re.compile(
    r"\b(" + "|".join(_PAYMENT_CONTEXT_WORDS) + r")\w*\b", re.IGNORECASE
)
_CONTEXT_WINDOW_CHARS = 60


def _has_override_in_payment_context(text: str) -> bool:
    for pattern in _SOFT_OVERRIDE_KEYWORD_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            window = text[
                max(0, m.start() - _CONTEXT_WINDOW_CHARS):
                min(len(text), m.end() + _CONTEXT_WINDOW_CHARS)
            ]
            if _PAYMENT_CONTEXT_RE.search(window):
                return True
    return False


# Persuasion/social-engineering framing distinct enough to flag standalone.
_SOCIAL_ENGINEERING_PATTERNS = [
    r"rather than (a )?verification (round|step)",
    r"(single|one) (pass|step) rather than",
    r"mismatch\b.{0,60}\b(gateway|system|processor)'?s?\s+side",
    r"nothing is lost\b",
    r"(order slot|reservation) is held either way\b",
]

# "Do the payment action now" combined with "verify/check it later" in the
# same content is a stronger, more specific social-engineering signal than
# either half alone — deliberately narrower than a bare "process immediately"
# so it doesn't fire on ordinary fulfillment-speed language.
_ACTION_NOW_PATTERNS = [
    r"(push|process|complete|capture|settle|release) the payment\b",
    r"complete the capture\b",
    r"capture now\b",
    r"process it now\b",
    r"settle (it|this)\s+(now|today)\b",
]

_DEFER_CHECK_PATTERNS = [
    r"(verif|review|reconcil|confirm|check)\w*.{0,60}(after(wards)?|later|following|afterward)\b",
    r"(after(wards)?|later)\b.{0,60}(verif|review|reconcil|confirm|check)\w*",
    r"sort\w*.{0,30}paperwork.{0,20}afterwards\b",
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
