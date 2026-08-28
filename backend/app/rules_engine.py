"""Deterministic mandate-vs-transaction gate.

No LLM call, no external API call, anywhere in evaluate(). String/pattern
matching only. If a case seems to need judgment an LLM would provide,
that's a signal to flag it to the user, not to add one.

The checks themselves now live in the standalone `mandate-guard` package
(packages/mandate-guard) so the gate can be used without the MandateCheck
app. This module stays as the app's import point — `app.rules_engine.evaluate`
and `app.rules_engine.Decision` keep working exactly as before — but holds no
copy of the logic, so the two can't drift apart.
"""

from mandate_guard.engine import evaluate
from mandate_guard.types import Decision

__all__ = ["Decision", "evaluate"]
