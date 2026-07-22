"""Razorpay test-mode integration: only ever called after an ALLOW verdict.

Guards routes/transactions.py's post-decision wiring, not rules_engine.py —
these tests never touch the rules engine's decision logic itself.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app import razorpay_client
from app.db import get_db
from app.main import app
from app.models import Mandate
from app.routes import transactions as transactions_route

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


def make_mandate_row(**overrides) -> Mandate:
    defaults = dict(
        mandate_id=uuid.uuid4(),
        user_id="u1",
        agent_id="agent1",
        agent_platform="chatgpt",
        agent_display_name="Shopping Assistant",
        created_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=30),
        status="active",
        max_amount_per_txn=1000,
        max_amount_per_window=2000,
        window_duration="24h",
        max_amount_total=5000,
        merchant_allowlist=["amazon"],
        category_allowlist=["groceries"],
        allowed_time_window={"start_hour": 6, "end_hour": 22},
        original_intent_text="Order groceries from Amazon up to 1000 rupees.",
        user_facing_summary="Groceries via Amazon, up to 1000 per order.",
    )
    defaults.update(overrides)
    return Mandate(**defaults)


class FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def scalar(self):
        return 0


class FakeSession:
    """No real DB: get() returns the fixed mandate row, all aggregate
    queries return empty/zero (no prior transactions), add()/commit()
    record what was persisted so tests can assert on it."""

    def __init__(self, mandate_row: Mandate) -> None:
        self.mandate_row = mandate_row
        self.added: list = []
        self.committed = False

    def get(self, model, pk):
        return self.mandate_row

    def query(self, *args, **kwargs):
        return FakeQuery()

    def add(self, row) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        pass


@pytest.fixture
def fake_session():
    session = FakeSession(make_mandate_row())
    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.pop(get_db, None)


def _post_transaction(client: TestClient, mandate_row: Mandate, **overrides):
    body = dict(
        transaction_id=str(uuid.uuid4()),
        mandate_id=str(mandate_row.mandate_id),
        proposed_amount=500.0,
        merchant_id="amazon",
        category="groceries",
        timestamp=NOW.isoformat(),
        source_content="Order groceries from Amazon up to 1000 rupees.",
        agent_reasoning="Buying weekly groceries as instructed.",
    )
    body.update(overrides)
    return client.post("/evaluate_transaction", json=body)


def test_blocked_transaction_never_calls_razorpay(fake_session, monkeypatch):
    mock_create_order = AsyncMock()
    monkeypatch.setattr(transactions_route.razorpay_client, "create_order", mock_create_order)

    client = TestClient(app)
    # amount exceeds max_amount_per_txn (1000) -> rules engine blocks
    resp = _post_transaction(client, fake_session.mandate_row, proposed_amount=5000.0)

    assert resp.status_code == 200
    data = resp.json()
    assert data["outcome"] == "block"
    assert data["razorpay_status"] == "BLOCKED"
    assert data["razorpay_order_id"] is None
    mock_create_order.assert_not_called()
    assert fake_session.added[0].razorpay_status == "BLOCKED"


def test_allowed_transaction_creates_order_and_stores_id(fake_session, monkeypatch):
    mock_create_order = AsyncMock(return_value={"id": "order_test_abc123"})
    monkeypatch.setattr(transactions_route.razorpay_client, "create_order", mock_create_order)

    client = TestClient(app)
    resp = _post_transaction(client, fake_session.mandate_row)

    assert resp.status_code == 200
    data = resp.json()
    assert data["outcome"] == "allow"
    assert data["razorpay_status"] == "ALLOWED_AND_SENT"
    assert data["razorpay_order_id"] == "order_test_abc123"
    mock_create_order.assert_called_once()
    assert fake_session.added[0].razorpay_order_id == "order_test_abc123"
    assert fake_session.added[0].razorpay_status == "ALLOWED_AND_SENT"


def test_razorpay_api_error_maps_to_error_status_not_a_block(fake_session, monkeypatch):
    mock_create_order = AsyncMock(
        side_effect=razorpay_client.RazorpayAPIError(500, "internal error")
    )
    monkeypatch.setattr(transactions_route.razorpay_client, "create_order", mock_create_order)

    client = TestClient(app)
    resp = _post_transaction(client, fake_session.mandate_row)

    assert resp.status_code == 200
    data = resp.json()
    # Rules-engine verdict is unchanged: still "allow". Only the delivery
    # side reflects the Razorpay failure — never conflated with a block.
    assert data["outcome"] == "allow"
    assert data["razorpay_status"] == "RAZORPAY_ERROR"
    assert data["razorpay_order_id"] is None
    assert fake_session.added[0].razorpay_status == "RAZORPAY_ERROR"


def test_razorpay_timeout_maps_to_error_status(fake_session, monkeypatch):
    mock_create_order = AsyncMock(side_effect=razorpay_client.RazorpayTimeoutError("timed out"))
    monkeypatch.setattr(transactions_route.razorpay_client, "create_order", mock_create_order)

    client = TestClient(app)
    resp = _post_transaction(client, fake_session.mandate_row)

    assert resp.status_code == 200
    data = resp.json()
    assert data["outcome"] == "allow"
    assert data["razorpay_status"] == "RAZORPAY_ERROR"
    assert data["razorpay_order_id"] is None
