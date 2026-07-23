"""POST /evaluate_transaction — DB-facing wrapper around rules_engine.evaluate().

This module is still part of the decision path: no LLM call, no external
API call, anywhere below. It only translates DB rows <-> domain.py
dataclasses and feeds DB-derived context into the deterministic check.
"""

import json
import logging
import os
import uuid
from datetime import datetime, time, timedelta

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, ConfigDict
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import advisory, ambiguity, domain, razorpay_client, rules_engine
from app.db import get_db
from app.models import Mandate, TransactionLog

logger = logging.getLogger(__name__)

# Exported so main.py can do:
#   app.state.limiter = limiter
#   app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


class ConnectionManager:
    """In-memory registry of live WebSocket clients for a single instance.

    No pub/sub, no Redis: broadcasting a decision just means looping over
    this process's own open connections. If this ever needs to fan out
    across multiple instances, that's a different piece of infrastructure
    and should be flagged, not silently grown here.
    """

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws/transactions")
async def websocket_transactions(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


class TransactionRequestIn(BaseModel):
    transaction_id: uuid.UUID
    mandate_id: uuid.UUID
    proposed_amount: float
    merchant_id: str
    category: str
    timestamp: datetime
    source_content: str
    agent_reasoning: str
    # "manual" | "demo" | "agent" — who/what initiated this request. Never
    # read by rules_engine.py or the Razorpay call; purely a DB tag so
    # scripted/agent-driven traffic is identifiable after the fact.
    source: str = "manual"


class TransactionDecisionOut(BaseModel):
    transaction_id: uuid.UUID
    outcome: str
    reason: str
    flagged: bool
    flag_reason: str | None
    razorpay_status: str
    razorpay_order_id: str | None


class TransactionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mandate_id: uuid.UUID
    transaction_id: uuid.UUID
    decision: str
    reason: str | None
    flagged: bool
    flag_reason: str | None
    timestamp: datetime
    merchant_id: str
    proposed_amount: float
    razorpay_status: str | None
    razorpay_order_id: str | None
    source: str
    llm_review_flagged: bool
    llm_advisory_note: str | None


class TransactionHistoryOut(BaseModel):
    items: list[TransactionHistoryItem]


@router.get("/transactions", response_model=TransactionHistoryOut)
def list_transactions(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> TransactionHistoryOut:
    rows = (
        db.query(TransactionLog)
        .order_by(TransactionLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    return TransactionHistoryOut(
        items=[TransactionHistoryItem.model_validate(row) for row in rows]
    )


def _parse_window_duration_seconds(window_duration: str) -> float:
    """Parse strings like '7d', '24h', '30m', '3600s' into seconds."""
    unit_seconds = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    suffix = window_duration[-1]
    if suffix in unit_seconds:
        return float(window_duration[:-1]) * unit_seconds[suffix]
    return float(window_duration)


def _mandate_row_to_domain(row: Mandate) -> domain.Mandate:
    start_hour = row.allowed_time_window["start_hour"]
    end_hour = row.allowed_time_window["end_hour"]
    return domain.Mandate(
        mandate_id=str(row.mandate_id),
        user_id=row.user_id,
        agent_id=row.agent_id,
        agent_platform=row.agent_platform,
        agent_display_name=row.agent_display_name,
        created_at=row.created_at,
        expires_at=row.expires_at,
        status=row.status,
        max_amount_per_txn=float(row.max_amount_per_txn),
        max_amount_per_window=float(row.max_amount_per_window),
        window_duration=_parse_window_duration_seconds(row.window_duration),
        max_amount_total=float(row.max_amount_total),
        merchant_allowlist=row.merchant_allowlist,
        category_allowlist=row.category_allowlist,
        allowed_time_window=(time(start_hour, 0), time(end_hour, 0)),
        original_intent_text=row.original_intent_text,
        user_facing_summary=row.user_facing_summary,
    )


def _request_to_domain(req: TransactionRequestIn) -> domain.TransactionRequest:
    return domain.TransactionRequest(
        transaction_id=str(req.transaction_id),
        mandate_id=str(req.mandate_id),
        proposed_amount=req.proposed_amount,
        merchant_id=req.merchant_id,
        category=req.category,
        timestamp=req.timestamp,
        source_content=req.source_content,
        agent_reasoning=req.agent_reasoning,
    )


def _build_context(
    db: Session, mandate_row: Mandate, req: TransactionRequestIn, window_seconds: float
) -> tuple[dict, bool]:
    already_logged = (
        db.query(TransactionLog.transaction_id)
        .filter(
            TransactionLog.mandate_id == mandate_row.mandate_id,
            TransactionLog.transaction_id == req.transaction_id,
        )
        .first()
        is not None
    )
    seen_transaction_ids = {str(req.transaction_id)} if already_logged else set()

    window_start = req.timestamp - timedelta(seconds=window_seconds)
    window_total = (
        db.query(func.coalesce(func.sum(TransactionLog.proposed_amount), 0))
        .filter(
            TransactionLog.mandate_id == mandate_row.mandate_id,
            TransactionLog.decision == "allow",
            TransactionLog.timestamp >= window_start,
        )
        .scalar()
    )
    lifetime_total = (
        db.query(func.coalesce(func.sum(TransactionLog.proposed_amount), 0))
        .filter(
            TransactionLog.mandate_id == mandate_row.mandate_id,
            TransactionLog.decision == "allow",
        )
        .scalar()
    )

    context = {
        "now": req.timestamp,
        "seen_transaction_ids": seen_transaction_ids,
        "window_total": float(window_total),
        "lifetime_total": float(lifetime_total),
    }
    return context, already_logged


async def _evaluate_and_persist(
    body: TransactionRequestIn, db: Session
) -> TransactionDecisionOut:
    """The actual decision pipeline: rules engine -> (maybe) Razorpay -> log
    -> broadcast. Shared by /evaluate_transaction and /demo/run so a demo
    run exercises exactly this code, not a parallel copy of it."""
    request_id = str(uuid.uuid4())

    # Fail closed: any unhandled error between here and the commit must
    # surface as a rejection, never as an "allow" the caller could act on.
    try:
        mandate_row = db.get(Mandate, body.mandate_id)
        if mandate_row is None:
            raise HTTPException(status_code=404, detail="mandate not found")

        domain_mandate = _mandate_row_to_domain(mandate_row)
        domain_txn = _request_to_domain(body)
        window_seconds = domain_mandate.window_duration
        context, already_logged = _build_context(db, mandate_row, body, window_seconds)

        decision = rules_engine.evaluate(domain_txn, domain_mandate, context)
        outcome = decision.outcome.lower()

        # Pure, deterministic classification — no I/O, cannot change
        # `decision` above. Only decides whether an advisory LLM call
        # happens AFTER this BLOCK is committed, further down.
        ambiguity_result = ambiguity.is_ambiguous_block(
            decision, domain_txn, domain_mandate, context
        )

        # Razorpay is called strictly after the rules-engine verdict, and
        # strictly only on "allow" — a blocked transaction must never reach
        # this call. A Razorpay-side failure (timeout/4xx/5xx) is its own
        # distinct state, not a MandateCheck block: the decision stays
        # "allow", only razorpay_status reflects the delivery failure.
        razorpay_order_id: str | None = None
        if outcome == "block":
            razorpay_status = "BLOCKED"
        else:
            try:
                order = await razorpay_client.create_order(
                    amount_rupees=body.proposed_amount,
                    currency="INR",
                    receipt=str(body.transaction_id),
                )
                razorpay_order_id = order.get("id")
                razorpay_status = "ALLOWED_AND_SENT"
            except razorpay_client.RazorpayError:
                logger.exception(
                    json.dumps(
                        {
                            "timestamp": datetime.utcnow().isoformat(),
                            "request_id": request_id,
                            "mandate_id": str(body.mandate_id),
                            "transaction_id": str(body.transaction_id),
                            "event": "razorpay_order_creation_failed",
                        }
                    )
                )
                razorpay_status = "RAZORPAY_ERROR"

        # transaction_id is the client-generated PK; a replay reuses the same
        # id, so there's nothing new to persist — the original row already
        # holds the first decision.
        if not already_logged:
            log_row = TransactionLog(
                transaction_id=body.transaction_id,
                mandate_id=body.mandate_id,
                proposed_amount=body.proposed_amount,
                merchant_id=body.merchant_id,
                category=body.category,
                timestamp=body.timestamp,
                source_content=body.source_content,
                agent_reasoning=body.agent_reasoning,
                decision=outcome,
                reason=decision.reason,
                flagged=decision.flagged,
                flag_reason=decision.flag_reason,
                razorpay_status=razorpay_status,
                razorpay_order_id=razorpay_order_id,
                source=body.source,
                llm_review_flagged=ambiguity_result.is_ambiguous,
            )
            db.add(log_row)
            db.commit()
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            json.dumps(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": request_id,
                    "mandate_id": str(body.mandate_id),
                    "decision": "block",
                    "reason": "internal error during evaluation (fail closed)",
                }
            )
        )
        raise HTTPException(
            status_code=503,
            detail="internal error during evaluation; transaction blocked (fail closed)",
        )

    await manager.broadcast(
        {
            "type": "transaction",
            "mandate_id": str(body.mandate_id),
            "transaction_id": str(body.transaction_id),
            "decision": outcome,
            "reason": decision.reason,
            "flagged": decision.flagged,
            "flag_reason": decision.flag_reason,
            "timestamp": body.timestamp.isoformat(),
            "merchant_id": body.merchant_id,
            "proposed_amount": body.proposed_amount,
            "razorpay_status": razorpay_status,
            "razorpay_order_id": razorpay_order_id,
            "source": body.source,
            "llm_review_flagged": ambiguity_result.is_ambiguous,
            "llm_advisory_note": None,
        }
    )

    logger.info(
        json.dumps(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": request_id,
                "mandate_id": str(body.mandate_id),
                "decision": outcome,
                "reason": decision.reason,
            }
        )
    )

    # Advisory-only: everything above (decision, DB commit, broadcast) is
    # already final. Nothing below this line can change it — on any
    # failure here, the BLOCK stands exactly as already persisted.
    if not already_logged and ambiguity_result.is_ambiguous:
        logger.info(
            json.dumps(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": request_id,
                    "transaction_id": str(body.transaction_id),
                    "event": "block_flagged_for_review",
                    "matched_condition": ambiguity_result.matched_condition,
                }
            )
        )
        note = advisory.request_advisory_opinion(
            domain_txn, domain_mandate, decision, ambiguity_result.matched_condition
        )
        if note is not None:
            db.query(TransactionLog).filter(
                TransactionLog.transaction_id == body.transaction_id
            ).update({"llm_advisory_note": note})
            db.commit()
            logger.info(
                json.dumps(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "request_id": request_id,
                        "transaction_id": str(body.transaction_id),
                        "event": "advisory_opinion_received",
                        "binding": False,
                        "note": note,
                    }
                )
            )
            await manager.broadcast(
                {
                    "type": "advisory_update",
                    "transaction_id": str(body.transaction_id),
                    "llm_advisory_note": note,
                }
            )
        else:
            logger.info(
                json.dumps(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "request_id": request_id,
                        "transaction_id": str(body.transaction_id),
                        "event": "advisory_call_failed",
                        "fallback": "none - BLOCK decision already persisted, unaffected",
                    }
                )
            )

    return TransactionDecisionOut(
        transaction_id=body.transaction_id,
        outcome=outcome,
        reason=decision.reason,
        flagged=decision.flagged,
        flag_reason=decision.flag_reason,
        razorpay_status=razorpay_status,
        razorpay_order_id=razorpay_order_id,
    )


@router.post("/evaluate_transaction", response_model=TransactionDecisionOut)
# Default 20/minute; RATE_LIMIT_EVALUATE exists so a busy demo (shared venue
# Wi-Fi behind one NAT IP) can be bumped from the deploy env without a code
# change — e.g. "100/minute" for event day, then removed.
@limiter.limit(os.environ.get("RATE_LIMIT_EVALUATE", "20/minute"))
async def evaluate_transaction(
    request: Request, body: TransactionRequestIn, db: Session = Depends(get_db)
) -> TransactionDecisionOut:
    return await _evaluate_and_persist(body, db)
