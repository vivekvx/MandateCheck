import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MandateCreate(BaseModel):
    user_id: str
    agent_id: str
    agent_platform: str
    agent_display_name: str
    expires_at: datetime
    max_amount_per_txn: float
    max_amount_per_window: float
    window_duration: str
    max_amount_total: float
    merchant_allowlist: list[str]
    category_allowlist: list[str]
    allowed_time_window: dict
    original_intent_text: str
    user_facing_summary: str


class MandateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mandate_id: uuid.UUID
    user_id: str
    agent_id: str
    agent_platform: str
    agent_display_name: str
    created_at: datetime
    expires_at: datetime
    status: str
    max_amount_per_txn: float
    max_amount_per_window: float
    window_duration: str
    max_amount_total: float
    merchant_allowlist: list[str]
    category_allowlist: list[str]
    allowed_time_window: dict
    original_intent_text: str
    user_facing_summary: str


class MandateListResponse(BaseModel):
    items: list[MandateResponse]
    limit: int
    offset: int
    total: int


class ParseIntentRequest(BaseModel):
    text: str


class ParseIntentResponse(BaseModel):
    merchant_allowlist: list[str]
    category_allowlist: list[str]
    max_amount_per_txn: float
    max_amount_per_window: float
    window_duration: str
    max_amount_total: float
    user_facing_summary: str
