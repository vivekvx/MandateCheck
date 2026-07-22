"""Razorpay test-mode Orders API client.

Deliberately isolated from rules_engine.py: this module is only ever called
*after* an ALLOW decision has already been made. It has no say in the
allow/block decision and must never be imported by rules_engine.py.

Test-mode keys only (RAZORPAY_TEST_KEY_ID / RAZORPAY_TEST_KEY_SECRET). There
is no live-key path here — that would be a separate, explicitly-approved
change, not something to grow into this module quietly.
"""

import os

import httpx

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"
_TIMEOUT_SECONDS = 10.0


class RazorpayError(Exception):
    """Base class for any failure creating a Razorpay order."""


class RazorpayTimeoutError(RazorpayError):
    pass


class RazorpayAPIError(RazorpayError):
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Razorpay API error {status_code}: {body}")


async def create_order(amount_rupees: float, currency: str, receipt: str) -> dict:
    """Create a test-mode Razorpay order. Raises RazorpayError subclasses on
    any failure (missing config, timeout, 4xx/5xx) — never returns a
    half-formed result."""
    try:
        key_id = os.environ["RAZORPAY_TEST_KEY_ID"]
        key_secret = os.environ["RAZORPAY_TEST_KEY_SECRET"]
    except KeyError as exc:
        raise RazorpayError(f"missing config: {exc}") from exc

    payload = {
        "amount": int(round(amount_rupees * 100)),  # Razorpay amount is in paise
        "currency": currency,
        "receipt": receipt,
        "payment_capture": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"{RAZORPAY_API_BASE}/orders",
                json=payload,
                auth=(key_id, key_secret),
            )
    except httpx.TimeoutException as exc:
        raise RazorpayTimeoutError(str(exc)) from exc
    except httpx.HTTPError as exc:
        raise RazorpayError(str(exc)) from exc

    if resp.status_code >= 400:
        raise RazorpayAPIError(resp.status_code, resp.text)

    return resp.json()
