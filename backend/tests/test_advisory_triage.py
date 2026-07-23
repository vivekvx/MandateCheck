"""Advisory-only LLM triage on ambiguous BLOCKs.

Guards the invariant: rules_engine.evaluate()'s decision is never altered
by the advisory call, regardless of what the LLM says or whether it fails.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

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
    def __init__(self, added):
        self._added = added

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None

    def scalar(self):
        return 0

    def update(self, values):
        if self._added:
            for key, value in values.items():
                setattr(self._added[0], key, value)


class FakeSession:
    def __init__(self, mandate_row: Mandate) -> None:
        self.mandate_row = mandate_row
        self.added: list = []
        self.committed = False

    def get(self, model, pk):
        return self.mandate_row

    def query(self, model):
        return FakeQuery(self.added)

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


def test_clear_allow_never_calls_llm(fake_session, monkeypatch):
    mock_create_order = AsyncMock(return_value={"id": "order_1"})
    monkeypatch.setattr(transactions_route.razorpay_client, "create_order", mock_create_order)
    with patch.object(transactions_route.advisory, "request_advisory_opinion") as mock_advisory:
        client = TestClient(app)
        resp = _post_transaction(client, fake_session.mandate_row, proposed_amount=500.0)
        assert resp.json()["outcome"] == "allow"
        mock_advisory.assert_not_called()
        assert fake_session.added[0].llm_review_flagged is False


def test_clear_block_never_calls_llm(fake_session, monkeypatch):
    mock_create_order = AsyncMock()
    monkeypatch.setattr(transactions_route.razorpay_client, "create_order", mock_create_order)
    with patch.object(transactions_route.advisory, "request_advisory_opinion") as mock_advisory:
        client = TestClient(app)
        # 5000 vs cap 1000 — nowhere near the 5% band, confidently over.
        resp = _post_transaction(client, fake_session.mandate_row, proposed_amount=5000.0)
        assert resp.json()["outcome"] == "block"
        mock_advisory.assert_not_called()
        assert fake_session.added[0].llm_review_flagged is False


def test_ambiguous_amount_triggers_llm_and_persists_note(fake_session, monkeypatch):
    monkeypatch.setattr(transactions_route.razorpay_client, "create_order", AsyncMock())
    with patch.object(
        transactions_route.advisory,
        "request_advisory_opinion",
        return_value="Would have allowed — only 2% over the per-transaction cap.",
    ) as mock_advisory:
        client = TestClient(app)
        # 1020 vs cap 1000 -> 2% over -> within the 5% ambiguous band.
        resp = _post_transaction(client, fake_session.mandate_row, proposed_amount=1020.0)

        assert resp.json()["outcome"] == "block"
        mock_advisory.assert_called_once()
        row = fake_session.added[0]
        assert row.llm_review_flagged is True
        assert row.llm_advisory_note == "Would have allowed — only 2% over the per-transaction cap."


def test_ambiguous_block_stays_block_even_if_llm_says_would_allow(fake_session, monkeypatch):
    monkeypatch.setattr(transactions_route.razorpay_client, "create_order", AsyncMock())
    with patch.object(
        transactions_route.advisory,
        "request_advisory_opinion",
        return_value="I would have allowed this transaction.",
    ):
        client = TestClient(app)
        resp = _post_transaction(client, fake_session.mandate_row, proposed_amount=1020.0)

        # The advisory opinion says "allow" — the persisted decision must
        # still be block. This is the core invariant this feature exists to
        # protect.
        assert resp.json()["outcome"] == "block"
        assert fake_session.added[0].decision == "block"


def test_advisory_failure_does_not_affect_already_persisted_block(fake_session, monkeypatch):
    monkeypatch.setattr(transactions_route.razorpay_client, "create_order", AsyncMock())
    with patch.object(
        transactions_route.advisory, "request_advisory_opinion", return_value=None
    ) as mock_advisory:
        client = TestClient(app)
        resp = _post_transaction(client, fake_session.mandate_row, proposed_amount=1020.0)

        assert resp.status_code == 200
        assert resp.json()["outcome"] == "block"
        mock_advisory.assert_called_once()
        row = fake_session.added[0]
        assert row.decision == "block"
        assert row.llm_review_flagged is True
        assert row.llm_advisory_note is None
