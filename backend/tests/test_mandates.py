"""Ownership check on POST /mandates/{mandate_id}/revoke.

Regression guard for a manual-code-review finding: revoke previously took
only mandate_id and revoked whatever mandate_id was handed to it, with no
check that the caller's user_id matched the mandate's owner. Fixed in
routes/mandates.py to require a user_id query param and 404 (not 403) on
mismatch, so as not to reveal that the mandate exists under a different
owner.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Mandate

NOW = datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc)


def make_mandate_row(**overrides) -> Mandate:
    defaults = dict(
        mandate_id=uuid.uuid4(),
        user_id="owner-user",
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


class FakeSession:
    """No real DB: get() always returns the fixed mandate row regardless
    of the pk asked for, mirroring the pattern used in
    test_razorpay_integration.py."""

    def __init__(self, mandate_row: Mandate) -> None:
        self.mandate_row = mandate_row
        self.committed = False

    def get(self, model, pk):
        return self.mandate_row

    def commit(self) -> None:
        self.committed = True

    def refresh(self, row) -> None:
        pass

    def close(self) -> None:
        pass


@pytest.fixture
def fake_session():
    session = FakeSession(make_mandate_row())
    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.pop(get_db, None)


def test_revoke_with_wrong_user_id_returns_404_and_does_not_revoke(fake_session):
    client = TestClient(app)
    mandate_id = fake_session.mandate_row.mandate_id

    resp = client.post(
        f"/mandates/{mandate_id}/revoke",
        params={"user_id": "attacker-user"},
    )

    assert resp.status_code == 404
    assert fake_session.mandate_row.status == "active"
    assert fake_session.committed is False


def test_revoke_with_correct_user_id_succeeds(fake_session):
    client = TestClient(app)
    mandate_id = fake_session.mandate_row.mandate_id

    resp = client.post(
        f"/mandates/{mandate_id}/revoke",
        params={"user_id": "owner-user"},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "revoked"
    assert fake_session.mandate_row.status == "revoked"
    assert fake_session.committed is True
