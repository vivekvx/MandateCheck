import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Mandate
from app.schemas import MandateCreate, MandateListResponse, MandateResponse

router = APIRouter()

MANDATE_COLUMNS = (
    Mandate.mandate_id,
    Mandate.user_id,
    Mandate.agent_id,
    Mandate.agent_platform,
    Mandate.agent_display_name,
    Mandate.created_at,
    Mandate.expires_at,
    Mandate.status,
    Mandate.max_amount_per_txn,
    Mandate.max_amount_per_window,
    Mandate.window_duration,
    Mandate.max_amount_total,
    Mandate.merchant_allowlist,
    Mandate.category_allowlist,
    Mandate.allowed_time_window,
    Mandate.original_intent_text,
    Mandate.user_facing_summary,
)


@router.post("/mandates", response_model=MandateResponse, status_code=201)
def create_mandate(payload: MandateCreate, db: Session = Depends(get_db)):
    mandate = Mandate(**payload.model_dump())
    db.add(mandate)
    db.commit()
    db.refresh(mandate)
    return mandate


@router.get("/mandates/{mandate_id}", response_model=MandateResponse)
def get_mandate(mandate_id: uuid.UUID, db: Session = Depends(get_db)):
    mandate = db.execute(
        select(*MANDATE_COLUMNS).where(Mandate.mandate_id == mandate_id)
    ).first()
    if mandate is None:
        raise HTTPException(status_code=404, detail="mandate not found")
    return mandate


@router.get("/mandates", response_model=MandateListResponse)
def list_mandates(
    user_id: str = Query(...),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    total = db.execute(
        select(Mandate.mandate_id).where(Mandate.user_id == user_id)
    ).all()
    rows = db.execute(
        select(*MANDATE_COLUMNS)
        .where(Mandate.user_id == user_id)
        .order_by(Mandate.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return MandateListResponse(items=rows, limit=limit, offset=offset, total=len(total))


@router.post("/mandates/{mandate_id}/revoke", response_model=MandateResponse)
def revoke_mandate(mandate_id: uuid.UUID, db: Session = Depends(get_db)):
    mandate = db.get(Mandate, mandate_id)
    if mandate is None:
        raise HTTPException(status_code=404, detail="mandate not found")
    mandate.status = "revoked"
    db.commit()
    db.refresh(mandate)
    return mandate
