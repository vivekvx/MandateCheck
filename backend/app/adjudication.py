"""Post-hoc claim triage.

NEVER executes a reversal or moves money — adjudicate() only ever produces
an AdjudicationResult, a recommendation object. Real fund reversal goes
through bank/network dispute infrastructure this project has no access to.

adjudicate() is deterministic, same boundary as rules_engine.evaluate():
no LLM call, no external API call, anywhere in it. If a case needs model
judgment to pick auto_approved vs auto_denied vs escalated, that's a signal
the case belongs in escalated — not a case to resolve with a model call.
"""

import json
import os
import re
import urllib.error
import urllib.request

from app.domain import AdjudicationResult, Claim, Mandate

# Small closed vocabulary used only to detect a claim naming an unauthorized
# merchant/category by name (e.g. "netflix" when the mandate never mentioned
# it). Deliberately not exhaustive — an unrecognized word just falls through
# to escalated rather than being auto-denied, which is the safe direction.
_KNOWN_MERCHANT_CATEGORY_VOCAB = {
    "netflix", "spotify", "uber", "amazon", "swiggy", "zomato", "flipkart",
    "shopping", "travel", "subscriptions", "electronics", "entertainment",
}


def _mismatch(merchant_id: str, category: str, mandate: Mandate) -> bool:
    return (
        merchant_id not in mandate.merchant_allowlist
        or category not in mandate.category_allowlist
    )


_FLAG_REASON_STOPWORDS = {
    "a", "the", "this", "that", "not", "is", "was", "known", "limitation",
    "case", "solved", "contains", "language", "style",
}


def _claim_aligns_with_flag_reason(claim_reason: str, flag_reason: str) -> bool:
    """Deterministic keyword overlap — same substring-matching style as
    rules_engine.py's own pattern checks, not NLP."""
    flag_words = {
        w for w in re.split(r"[^a-z0-9]+", flag_reason.lower())
        if len(w) >= 4 and w not in _FLAG_REASON_STOPWORDS
    }
    text = claim_reason.lower()
    return any(w in text for w in flag_words)


def _claim_cites_unauthorized_merchant_or_category(
    claim_reason: str, merchant_id: str, category: str, mandate: Mandate
) -> bool:
    authorized = (
        {m.lower() for m in mandate.merchant_allowlist}
        | {c.lower() for c in mandate.category_allowlist}
        | {merchant_id.lower(), category.lower()}
    )
    words = claim_reason.lower().replace(",", " ").split()
    return any(w in _KNOWN_MERCHANT_CATEGORY_VOCAB and w not in authorized for w in words)


def adjudicate(claim: Claim, transaction_log_row, mandate: Mandate) -> AdjudicationResult:
    """transaction_log_row needs: merchant_id, category, proposed_amount, decision,
    reason, flagged, flag_reason."""
    merchant_id = transaction_log_row.merchant_id
    category = transaction_log_row.category
    decision = transaction_log_row.decision
    flagged = transaction_log_row.flagged
    flag_reason = transaction_log_row.flag_reason or ""

    mismatch = _mismatch(merchant_id, category, mandate)

    # Category 1 — clear-cut auto-approve-reversal: the real scenario-8
    # pattern. Something executed (ALLOW) despite a known-suspicious signal
    # flagged at execution time, and the claim is actually about that same
    # signal. A blocked transaction never qualifies here — nothing executed,
    # so there's nothing to reverse. (Claims contesting a block would be a
    # different feature — not built here.)
    if decision == "allow" and flagged and flag_reason and _claim_aligns_with_flag_reason(
        claim.claim_reason, flag_reason
    ):
        return AdjudicationResult(
            status="auto_approved",
            recommendation="approve reversal",
            recommendation_basis=f"transaction was flagged at execution time: {flag_reason}",
        )

    # Category 2 — clear-cut auto-deny: the transaction was a plain allow,
    # not flagged, fully within mandate bounds, and the claim doesn't cite
    # anything the mandate itself didn't already explicitly authorize.
    if (
        decision == "allow"
        and not flagged
        and not mismatch
        and not _claim_cites_unauthorized_merchant_or_category(
            claim.claim_reason, merchant_id, category, mandate
        )
    ):
        return AdjudicationResult(
            status="auto_denied",
            recommendation="deny claim",
            recommendation_basis=(
                "transaction was within mandate bounds (allowed merchant/category, "
                "not flagged); claim does not cite anything the mandate did not "
                "already authorize"
            ),
        )

    # Category 3 — everything else, including any blocked transaction and
    # any allow+flagged claim that doesn't align with the recorded
    # flag_reason: no auto-decision, needs a human.
    return AdjudicationResult(
        status="escalated",
        recommendation="needs human review",
        recommendation_basis="does not meet deterministic auto-approve or auto-deny criteria",
    )


GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

_SUMMARY_SYSTEM_PROMPT = (
    "You write a short, plain-language summary of the mismatch between what "
    "a payment mandate authorized and what a transaction actually did, for a "
    "human reviewer to read quickly. Two sentences max. You are NOT deciding "
    "whether the claim is valid — never say approve, deny, or recommend "
    "anything. Only describe the mismatch."
)


def summarize_mismatch_for_review(
    original_intent_text: str, transaction_log_row
) -> str | None:
    """Escalated claims only. Plain-language SUMMARY for a human reviewer.

    Distinct from AdjudicationResult.recommendation on purpose — this
    function never returns an approve/deny decision, only a description.
    Returns None if not configured or on any failure (never blocks the
    escalation itself on this being unavailable).
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None

    model = os.environ.get("HARNESS_MODEL", "groq/llama-3.1-8b-instant")
    user_content = (
        f"Mandate authorized: {original_intent_text}\n"
        f"Transaction: merchant={transaction_log_row.merchant_id}, "
        f"category={transaction_log_row.category}, "
        f"amount={transaction_log_row.proposed_amount}, "
        f"decision={transaction_log_row.decision}, reason={transaction_log_row.reason}"
    )
    body = {
        "model": model.removeprefix("groq/"),
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SUMMARY_SYSTEM_PROMPT},
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
        with urllib.request.urlopen(req, timeout=20) as resp:
            completion = json.load(resp)
        return completion["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError):
        return None
