"""POST /agent/run — a real LLM autonomously attempts purchases against a
real mandate, through the real evaluation pipeline.

Unlike /demo/run (fixed, scripted inputs), the transactions here come from
an actual model call each turn — see agent_runner.py for the loop and the
invariant it protects (the model proposes, it never decides allow/block).
"""

import json
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent_runner import AgentRunnerError, run_agent
from app.db import get_db
from app.routes.transactions import TransactionDecisionOut, limiter

logger = logging.getLogger(__name__)

router = APIRouter()


class AgentAttemptOut(BaseModel):
    attempt: int
    action: str
    reasoning: str
    merchant_id: str | None
    category: str | None
    amount: float | None
    result: TransactionDecisionOut | None


class AgentRunResponse(BaseModel):
    mandate_id: uuid.UUID
    attempts: list[AgentAttemptOut]


@router.post("/agent/run", response_model=AgentRunResponse)
@limiter.limit(os.environ.get("RATE_LIMIT_AGENT_RUN", "5/minute"))
async def run_agent_endpoint(request: Request, db: Session = Depends(get_db)) -> AgentRunResponse:
    request_id = str(uuid.uuid4())
    logger.info(
        json.dumps(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": request_id,
                "event": "agent_run_started",
            }
        )
    )

    try:
        mandate_id, attempts = await run_agent(db)
    except AgentRunnerError as exc:
        logger.exception(
            json.dumps(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": request_id,
                    "event": "agent_run_failed",
                    "error": str(exc),
                }
            )
        )
        raise HTTPException(status_code=502, detail=str(exc))

    logger.info(
        json.dumps(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": request_id,
                "mandate_id": str(mandate_id),
                "event": "agent_run_finished",
                "attempt_count": len(attempts),
            }
        )
    )

    return AgentRunResponse(
        mandate_id=mandate_id,
        attempts=[
            AgentAttemptOut(
                attempt=a.attempt,
                action=a.action,
                reasoning=a.reasoning,
                merchant_id=a.merchant_id,
                category=a.category,
                amount=a.amount,
                result=a.result,
            )
            for a in attempts
        ],
    )
