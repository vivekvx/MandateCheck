"""Genuine-concurrency regression tests for the two races fixed in
routes/transactions.py:

1. Spend-cap TOCTOU: concurrent requests against the same mandate must not
   all read the same pre-spend total and all pass a cap only one of them
   fits under.
2. Replay TOCTOU: concurrent requests carrying the same transaction_id must
   not all see "not seen yet" and all get processed.

These races only exist at the real Postgres level (row locks, unique
constraints) — every other test file in this suite uses an in-memory
FakeSession precisely because it doesn't need real DB semantics. These
tests deliberately do, so they talk to the actual dockerized Postgres
directly via SessionLocal, bypassing the HTTP/ASGI layer entirely.

They also bypass FastAPI's TestClient on purpose: TestClient requests
funnel through one shared anyio portal/event loop, and the code under test
makes plain blocking psycopg2 calls (not awaited) inside an `async def` —
those calls block that one event loop thread for their whole duration, so
two TestClient calls can never actually be in-flight against Postgres at
the same moment, no matter how they're submitted. Calling
_evaluate_and_persist directly from N separate OS threads, each running
its own asyncio.run() and its own real DB session, is what actually gets
concurrent execution reaching Postgres at the same time.
"""

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.db import SessionLocal
from app.models import Mandate, TransactionLog
from app.routes import transactions as transactions_route

MERCHANT = "amazon"
CATEGORY = "groceries"


def _make_mandate_row(**overrides) -> Mandate:
    defaults = dict(
        mandate_id=uuid.uuid4(),
        user_id="concurrency-test",
        agent_id="agent1",
        agent_platform="chatgpt",
        agent_display_name="Concurrency Test Agent",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        status="active",
        max_amount_per_txn=1000,
        max_amount_per_window=100,
        window_duration="24h",
        max_amount_total=100_000,
        merchant_allowlist=[MERCHANT],
        category_allowlist=[CATEGORY],
        # Full-day window: real wall-clock time is used as "now" (that's
        # the fix), so the test must tolerate whatever hour it runs at.
        allowed_time_window={"start_hour": 0, "end_hour": 23},
        original_intent_text="Order groceries from Amazon.",
        user_facing_summary="Groceries via Amazon.",
    )
    defaults.update(overrides)
    return Mandate(**defaults)


@pytest.fixture
def real_mandate():
    """A real row in the real Postgres instance this stack runs against —
    the races under test only exist at that level."""
    session = SessionLocal()
    row = _make_mandate_row()
    session.add(row)
    session.commit()
    mandate_id = row.mandate_id
    session.close()

    yield mandate_id

    cleanup = SessionLocal()
    cleanup.query(TransactionLog).filter(TransactionLog.mandate_id == mandate_id).delete()
    cleanup.query(Mandate).filter(Mandate.mandate_id == mandate_id).delete()
    cleanup.commit()
    cleanup.close()


def _fire(mandate_id, transaction_id, proposed_amount):
    """One full evaluate+persist call, on its own DB session, in its own
    event loop, in whatever OS thread the caller runs this in."""
    body = transactions_route.TransactionRequestIn(
        transaction_id=transaction_id,
        mandate_id=mandate_id,
        proposed_amount=proposed_amount,
        merchant_id=MERCHANT,
        category=CATEGORY,
        timestamp=datetime.now(timezone.utc),
        source_content="Order groceries from Amazon.",
        agent_reasoning="Buying groceries as instructed.",
    )
    session = SessionLocal()
    try:
        return asyncio.run(transactions_route._evaluate_and_persist(body, session))
    finally:
        session.close()


def test_concurrent_requests_never_exceed_window_cap(real_mandate, monkeypatch):
    """5 concurrent requests of 60 each against a window cap of 100. Only
    one can legitimately fit (60 <= 100; a second 60 would make 120 > 100).
    Pre-fix, each request's SELECT SUM can race ahead of every other
    request's INSERT, so more than one can read window_total=0 and pass.
    """
    monkeypatch.setattr(
        transactions_route.razorpay_client,
        "create_order",
        AsyncMock(return_value={"id": "order_cap_test"}),
    )
    n = 5
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [
            pool.submit(_fire, real_mandate, uuid.uuid4(), 60.0) for _ in range(n)
        ]
        results = [f.result() for f in as_completed(futures)]

    allowed = [r for r in results if r.outcome == "allow"]
    blocked = [r for r in results if r.outcome == "block"]

    # Not "most of them" — exactly the number that actually fits.
    assert len(allowed) == 1
    assert len(blocked) == n - 1
    assert len(allowed) * 60.0 <= 100.0
    for r in blocked:
        assert "max_amount_per_window" in r.reason


def test_concurrent_identical_transaction_id_processed_exactly_once(real_mandate, monkeypatch):
    """8 concurrent requests, identical transaction_id. Pre-fix, a pre-check
    SELECT lets every one of them see "not seen yet" and all get processed
    (and, worse, all call Razorpay). Exactly one must win, every run.
    """
    monkeypatch.setattr(
        transactions_route.razorpay_client,
        "create_order",
        AsyncMock(return_value={"id": "order_replay_test"}),
    )
    n = 8
    txn_id = uuid.uuid4()
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [pool.submit(_fire, real_mandate, txn_id, 10.0) for _ in range(n)]
        results = [f.result() for f in as_completed(futures)]

    replayed = [r for r in results if r.reason == "replay: transaction_id already seen"]
    processed = [r for r in results if r.reason != "replay: transaction_id already seen"]

    assert len(processed) == 1
    assert len(replayed) == n - 1

    session = SessionLocal()
    try:
        count = (
            session.query(TransactionLog)
            .filter(TransactionLog.transaction_id == txn_id)
            .count()
        )
    finally:
        session.close()
    assert count == 1
