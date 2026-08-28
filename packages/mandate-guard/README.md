# mandate-guard

A deterministic gate that checks an AI agent's payment request against a user-defined mandate before it executes — no LLM call in the decision path.

## Usage

```python
from mandate_guard import Mandate, TransactionRequest, evaluate

decision = evaluate(txn, mandate, context={"now": server_now, "window_total": 0.0})
if decision.outcome == "ALLOW":
    charge(txn)  # decision.flagged may still be True — surface it for review
```

`evaluate()` returns a `Decision` with `outcome` (`"ALLOW"` / `"BLOCK"`), `reason`, and the advisory `flagged` / `flag_reason` pair.

## Installation

```
pip install -e packages/mandate-guard
```

Not published to PyPI.

## Layout

- `engine.py` — `evaluate()`: the checks, in order
- `types.py` — `Mandate`, `TransactionRequest`, `Decision`
- `patterns.py` — injection/flag pattern definitions (checks 9 and 10)
- `guard.py` — server-authoritative clock, row locking, insert-first replay detection (needs a SQLAlchemy `Session`)

Part of the [MandateCheck](https://github.com/vivekvx/MandateCheck) project.
