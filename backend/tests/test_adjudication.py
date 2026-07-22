from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from app.adjudication import adjudicate
from app.domain import Claim, Mandate

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


@dataclass
class FakeTransactionLog:
    """Duck-types the TransactionLog columns adjudicate() reads."""

    merchant_id: str
    category: str
    proposed_amount: float
    decision: str
    reason: str
    flagged: bool = False
    flag_reason: str | None = None


def make_mandate(**overrides) -> Mandate:
    defaults = dict(
        mandate_id="m1",
        user_id="u1",
        agent_id="agent1",
        agent_platform="chatgpt",
        agent_display_name="Shopping Assistant",
        created_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=30),
        status="active",
        max_amount_per_txn=1000.0,
        max_amount_per_window=2000.0,
        window_duration=86400.0,
        max_amount_total=5000.0,
        merchant_allowlist=["amazon", "swiggy"],
        category_allowlist=["groceries", "food"],
        allowed_time_window=(time(6, 0), time(22, 0)),
        original_intent_text="Order groceries from Amazon up to 1000 rupees.",
        user_facing_summary="Groceries via Amazon, up to 1000 per order.",
    )
    defaults.update(overrides)
    return Mandate(**defaults)


def make_claim(**overrides) -> Claim:
    defaults = dict(
        claim_id="c1",
        transaction_id="t1",
        claim_reason="",
        created_at=NOW,
        status="pending",
    )
    defaults.update(overrides)
    return Claim(**defaults)


def test_allow_flagged_with_matching_claim_auto_approves_reversal():
    # Real scenario-8 pattern: rules_engine allowed it (within bounds) but
    # flagged it for an override-style signal in source_content. The claim
    # names that same signal — no ambiguity, safe to auto-approve reversal.
    txn = FakeTransactionLog(
        merchant_id="amazon",
        category="groceries",
        proposed_amount=500.0,
        decision="allow",
        reason="all checks passed",
        flagged=True,
        flag_reason=(
            "source_content contains override-style language; "
            "known limitation, not a solved case"
        ),
    )
    claim = make_claim(
        claim_reason="The agent used override language I never approved to push this through."
    )
    result = adjudicate(claim, txn, make_mandate())
    assert result.status == "auto_approved"
    assert result.recommendation == "approve reversal"


def test_plain_allow_within_bounds_auto_denies():
    # Allowed, not flagged, fully within mandate bounds; claim doesn't name
    # anything the mandate never authorized — nothing here for a human.
    txn = FakeTransactionLog(
        merchant_id="amazon",
        category="groceries",
        proposed_amount=500.0,
        decision="allow",
        reason="all checks passed",
        flagged=False,
    )
    claim = make_claim(claim_reason="I don't think I approved this purchase.")
    result = adjudicate(claim, txn, make_mandate())
    assert result.status == "auto_denied"
    assert result.recommendation == "deny claim"


def test_allow_within_bounds_but_claim_cites_unauthorized_merchant_escalates():
    # Ambiguous: the logged transaction is within mandate bounds, but the
    # claim itself brings up a different, unauthorized merchant (netflix) —
    # that's a case for a human, not an auto-deny guess.
    txn = FakeTransactionLog(
        merchant_id="amazon",
        category="groceries",
        proposed_amount=500.0,
        decision="allow",
        reason="all checks passed",
        flagged=False,
    )
    claim = make_claim(
        claim_reason="I was also charged for netflix, which isn't in my mandate at all."
    )
    result = adjudicate(claim, txn, make_mandate())
    assert result.status == "escalated"
    assert result.recommendation == "needs human review"


def test_blocked_transaction_never_produces_approve_reversal():
    # Nothing executed — a block means no money moved, so there's nothing
    # to reverse, regardless of what the claim says. Must escalate, never
    # auto-approve a reversal. (Blocked-transaction claims might deserve
    # their own "contest this block" category later — not this one.)
    txn = FakeTransactionLog(
        merchant_id="netflix",
        category="subscriptions",
        proposed_amount=500.0,
        decision="block",
        reason="merchant_id not in merchant_allowlist",
        flagged=False,
    )
    claim = make_claim(
        claim_reason="This charged netflix, which I never authorized in my mandate."
    )
    result = adjudicate(claim, txn, make_mandate())
    assert result.status != "auto_approved"
    assert result.recommendation != "approve reversal"
    assert result.status == "escalated"
