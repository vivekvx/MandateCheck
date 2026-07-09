from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.routes import health, mandates, transactions

app = FastAPI()

app.state.limiter = transactions.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(mandates.router)
app.include_router(health.router)
app.include_router(transactions.router)
