"""Server-authoritative clock, row locking, and insert-first replay
detection — extracted from routes/transactions.py.

Generic over the caller's ORM models: functions here take a Session plus
the specific Column objects and values they need, rather than importing
MandateCheck's Mandate/TransactionLog directly. This is the seed of a
future standalone guard package; storage abstraction beyond "a SQLAlchemy
Session" is deliberately out of scope for this pass — see
decisions/server-authoritative-clock-and-atomic-caps.md for the incident
this logic was written to fix.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Column, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def server_now() -> datetime:
    """The only authoritative clock for any expiry/time-window/spend-cap
    check. A caller-claimed timestamp must never be used here — it can be
    kept as an audit field, but never fed into a decision."""
    return datetime.now(timezone.utc)


def window_start(now: datetime, window_seconds: float) -> datetime:
    return now - timedelta(seconds=window_seconds)


def lock_row_for_update(
    db: Session, model: type, pk_column: Column, pk_value: Any
) -> None:
    """Take and hold a row lock (SELECT ... FOR UPDATE) for the rest of the
    caller's transaction, serializing concurrent evaluations against the
    same subject (e.g. the same mandate). Result discarded — call this
    only to take the lock; fetch the row itself separately. Without this,
    two concurrent requests against the same subject can both read the
    same pre-write totals via sum_amount_since below and both pass a cap
    only one of them should fit under."""
    db.query(model).filter(pk_column == pk_value).with_for_update().first()


def sum_amount_since(
    db: Session,
    key_column: Column,
    key_value: Any,
    amount_column: Column,
    decision_column: Column,
    decision_value: str,
    since: datetime | None = None,
    timestamp_column: Column | None = None,
) -> float:
    """Sum amount_column over rows matching key_column == key_value and
    decision_column == decision_value, optionally restricted to
    timestamp_column >= since. Caller must hold the subject's row lock
    (lock_row_for_update) before calling — otherwise this can read a total
    that's stale relative to a concurrent writer, the spend-cap TOCTOU
    race this module exists to close."""
    query = db.query(func.coalesce(func.sum(amount_column), 0)).filter(
        key_column == key_value,
        decision_column == decision_value,
    )
    if since is not None:
        query = query.filter(timestamp_column >= since)
    return float(query.scalar())


def insert_with_replay_detection(db: Session, row: Any) -> bool:
    """Insert-attempt-first replay detection: add row, flush, and treat a
    unique-constraint IntegrityError as the authoritative "already seen"
    signal rather than a pre-check SELECT (which can't be made safe
    against two genuinely concurrent requests carrying the same
    identifier — both would see "not seen yet" and both proceed). Returns
    True if this row was a replay (already existed) — the session is
    rolled back in that case, since whichever request won the race already
    committed its own copy. Returns False if the insert succeeded."""
    db.add(row)
    try:
        db.flush()
        return False
    except IntegrityError:
        db.rollback()
        return True
