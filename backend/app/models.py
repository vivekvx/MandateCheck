import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Mandate(Base):
    __tablename__ = "mandates"

    mandate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String, nullable=False)
    agent_platform: Mapped[str] = mapped_column(String, nullable=False)
    agent_display_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    max_amount_per_txn: Mapped[float] = mapped_column(Numeric, nullable=False)
    max_amount_per_window: Mapped[float] = mapped_column(Numeric, nullable=False)
    window_duration: Mapped[str] = mapped_column(String, nullable=False)
    max_amount_total: Mapped[float] = mapped_column(Numeric, nullable=False)
    merchant_allowlist: Mapped[list] = mapped_column(JSON, nullable=False)
    category_allowlist: Mapped[list] = mapped_column(JSON, nullable=False)
    allowed_time_window: Mapped[dict] = mapped_column(JSON, nullable=False)
    original_intent_text: Mapped[str] = mapped_column(Text, nullable=False)
    user_facing_summary: Mapped[str] = mapped_column(Text, nullable=False)


class TransactionLog(Base):
    __tablename__ = "transaction_logs"

    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    mandate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mandates.mandate_id"),
        index=True,
        nullable=False,
    )
    proposed_amount: Mapped[float] = mapped_column(Numeric, nullable=False)
    merchant_id: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), nullable=False)
    source_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    flag_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    # ALLOWED_AND_SENT | BLOCKED | RAZORPAY_ERROR — distinct from `decision`
    # (the rules-engine allow/block verdict, unchanged by this column).
    # Nullable: pre-existing rows predate the Razorpay integration.
    razorpay_status: Mapped[str | None] = mapped_column(String, nullable=True)
    razorpay_order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # "manual" | "demo" | "agent" — how this transaction was initiated,
    # distinct from `decision`. Never changes the evaluation code path.
    source: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    # Advisory-only layer, never a decision input: `decision` above is final
    # and persisted before either of these is touched. llm_review_flagged is
    # set synchronously/deterministically by ambiguity.is_ambiguous_block();
    # llm_advisory_note is filled in afterward (may stay null forever if the
    # advisory call fails — that failure never changes `decision`).
    llm_review_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_advisory_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transaction_logs.transaction_id"),
        index=True,
        nullable=False,
    )
    claim_reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    recommendation: Mapped[str | None] = mapped_column(String, nullable=True)
    recommendation_basis: Mapped[str | None] = mapped_column(Text, nullable=True)
