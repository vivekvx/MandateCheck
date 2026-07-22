"""POST /claims, GET /claims/{claim_id} — post-hoc claim triage.

This module NEVER executes a reversal or moves money. adjudicate() only
ever produces a recommendation object, clearly labeled as such. Real fund
reversal goes through bank/network dispute infrastructure this project has
no access to and does not pretend to have.
"""

import json
import logging
import os
import uuid
from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import domain
from app.adjudication import adjudicate, summarize_mismatch_for_review
from app.db import get_db
from app.models import Claim, Mandate, TransactionLog
from app.routes.transactions import limiter, _parse_window_duration_seconds

logger = logging.getLogger(__name__)

router = APIRouter()


class ClaimCreate(BaseModel):
    transaction_id: uuid.UUID
    claim_reason: str


class ClaimResponse(BaseModel):
    claim_id: uuid.UUID
    transaction_id: uuid.UUID
    claim_reason: str
    created_at: datetime
    status: str
    recommendation: str | None
    recommendation_basis: str | None
    # Plain-language mismatch description for a human reviewer, escalated
    # claims only. Never an approve/deny decision — kept separate from
    # `recommendation` on purpose so it can't be mistaken for one. Not
    # persisted: computed at request time, so GET never returns it.
    review_summary: str | None = None


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


@router.post("/claims", response_model=ClaimResponse, status_code=201)
@limiter.limit(os.environ.get("RATE_LIMIT_CLAIMS", "20/minute"))
def create_claim(request: Request, payload: ClaimCreate, db: Session = Depends(get_db)) -> ClaimResponse:
    txn_row = db.get(TransactionLog, payload.transaction_id)
    if txn_row is None:
        raise HTTPException(status_code=404, detail="transaction not found")

    mandate_row = db.get(Mandate, txn_row.mandate_id)
    if mandate_row is None:
        raise HTTPException(status_code=404, detail="mandate not found")

    mandate_domain = _mandate_row_to_domain(mandate_row)

    claim_row = Claim(
        transaction_id=payload.transaction_id,
        claim_reason=payload.claim_reason,
        status="pending",
    )

    claim_domain = domain.Claim(
        claim_id=str(uuid.uuid4()),
        transaction_id=str(payload.transaction_id),
        claim_reason=payload.claim_reason,
        created_at=datetime.utcnow(),
        status="pending",
    )
    result = adjudicate(claim_domain, txn_row, mandate_domain)

    claim_row.status = result.status
    claim_row.recommendation = result.recommendation
    claim_row.recommendation_basis = result.recommendation_basis

    db.add(claim_row)
    db.commit()
    db.refresh(claim_row)

    # Escalated only, and only ever a descriptive summary — never an
    # approve/deny decision. Not persisted, so this is computed fresh here
    # and returned only on this response, not on subsequent GETs.
    review_summary = None
    if result.status == "escalated":
        review_summary = summarize_mismatch_for_review(
            mandate_domain.original_intent_text, txn_row
        )

    logger.info(
        json.dumps(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "claim_id": str(claim_row.claim_id),
                "transaction_id": str(payload.transaction_id),
                "status": result.status,
            }
        )
    )
    return ClaimResponse(
        claim_id=claim_row.claim_id,
        transaction_id=claim_row.transaction_id,
        claim_reason=claim_row.claim_reason,
        created_at=claim_row.created_at,
        status=claim_row.status,
        recommendation=claim_row.recommendation,
        recommendation_basis=claim_row.recommendation_basis,
        review_summary=review_summary,
    )


@router.get("/claims/{claim_id}", response_model=ClaimResponse)
@limiter.limit(os.environ.get("RATE_LIMIT_CLAIMS", "20/minute"))
def get_claim(request: Request, claim_id: uuid.UUID, db: Session = Depends(get_db)) -> ClaimResponse:
    claim_row = db.get(Claim, claim_id)
    if claim_row is None:
        raise HTTPException(status_code=404, detail="claim not found")
    return ClaimResponse(
        claim_id=claim_row.claim_id,
        transaction_id=claim_row.transaction_id,
        claim_reason=claim_row.claim_reason,
        created_at=claim_row.created_at,
        status=claim_row.status,
        recommendation=claim_row.recommendation,
        recommendation_basis=claim_row.recommendation_basis,
        review_summary=None,
    )
