"""mandate-guard: a deterministic gate for AI-agent payment requests.

The allow/block decision is never made by a model — it is a fixed set of
checks, run in order, every time. No LLM call and no external API call
anywhere in evaluate().
"""

from mandate_guard.engine import evaluate
from mandate_guard.types import Decision, Mandate, TransactionRequest

__all__ = ["Decision", "Mandate", "TransactionRequest", "evaluate"]

__version__ = "0.1.0"
