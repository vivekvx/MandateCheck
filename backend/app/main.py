import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

# Without this, module-level `logging.getLogger(__name__).info(...)` calls
# throughout the app (agent_runner.py, transactions.py, demo.py, ...) hit a
# root logger with no handler and are silently dropped — they never reach
# `docker compose logs`. stdout, not stderr: docker compose logs shows both,
# but stdout keeps these interleaved with uvicorn's own request logs.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)

from app.routes import agent, claims, demo, health, mandates, transactions

app = FastAPI()

app.state.limiter = transactions.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:7009")],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(mandates.router)
app.include_router(health.router)
app.include_router(transactions.router)
app.include_router(claims.router)
app.include_router(demo.router)
app.include_router(agent.router)
