from dataclasses import dataclass
from datetime import datetime, time


@dataclass
class Mandate:
    mandate_id: str
    user_id: str
    agent_id: str
    agent_platform: str
    agent_display_name: str
    created_at: datetime
    expires_at: datetime
    status: str  # "active" | "revoked" | "expired"
    max_amount_per_txn: float
    max_amount_per_window: float
    window_duration: float  # seconds
    max_amount_total: float
    merchant_allowlist: list[str]
    category_allowlist: list[str]
    allowed_time_window: tuple[time, time]  # (start, end), inclusive
    original_intent_text: str
    user_facing_summary: str


@dataclass
class TransactionRequest:
    transaction_id: str
    mandate_id: str
    proposed_amount: float
    merchant_id: str
    category: str
    timestamp: datetime
    source_content: str
    agent_reasoning: str
