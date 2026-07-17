"""Fail-closed property of POST /evaluate_transaction.

If anything raises mid-evaluation (e.g. the DB dies during the
replay/window-total context queries), the endpoint must reject the
transaction — it must never return an "allow" and never log the
transaction as allowed. Guards the surrounding error handling in
routes/transactions.py, not rules_engine.py itself.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.main import app
from app.models import Mandate

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


def make_mandate_row() -> Mandate:
    return Mandate(
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


class ExplodingSession:
    """Finds the mandate, then raises on the first context-building query —
    simulates the DB going away mid-evaluation."""

    def __init__(self, mandate_row: Mandate) -> None:
        self.mandate_row = mandate_row
        self.added: list = []
        self.committed = False

    def get(self, model, pk):
        return self.mandate_row

    def query(self, *args, **kwargs):
        raise OperationalError("SELECT ...", {}, Exception("connection refused"))

    def add(self, row) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        pass


@pytest.fixture
def exploding_session():
    session = ExplodingSession(make_mandate_row())
    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.pop(get_db, None)


def test_internal_error_mid_evaluation_fails_closed(exploding_session):
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/evaluate_transaction",
        json={
            "transaction_id": str(uuid.uuid4()),
            "mandate_id": str(exploding_session.mandate_row.mandate_id),
            "proposed_amount": 500.0,
            "merchant_id": "amazon",
            "category": "groceries",
            "timestamp": NOW.isoformat(),
            "source_content": "Order groceries from Amazon up to 1000 rupees.",
            "agent_reasoning": "Buying weekly groceries as instructed.",
        },
    )

    # Explicit rejection, not an unhandled crash and never an allow.
    assert resp.status_code == 503
    assert "blocked" in resp.json()["detail"]
    assert '"outcome":"allow"' not in resp.text.replace(" ", "")

    # Nothing persisted as an allowed transaction.
    assert exploding_session.committed is False
    assert exploding_session.added == []
