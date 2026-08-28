"""Server-authoritative clock, row locking, and insert-first replay
detection — extracted from routes/transactions.py.

The implementations now live in the standalone `mandate-guard` package
(packages/mandate-guard). This module stays as the app's import point —
`app.guard.server_now`, `.window_start`, `.lock_row_for_update`,
`.sum_amount_since`, `.insert_with_replay_detection` keep working exactly as
before — but holds no copy of the logic, so the two can't drift apart. See
decisions/server-authoritative-clock-and-atomic-caps.md for the incident this
logic was written to fix.
"""

from mandate_guard.guard import (
    insert_with_replay_detection,
    lock_row_for_update,
    server_now,
    sum_amount_since,
    window_start,
)

__all__ = [
    "insert_with_replay_detection",
    "lock_row_for_update",
    "server_now",
    "sum_amount_since",
    "window_start",
]
