"""Reset the demo database to a clean, known state.

Deletes all existing claims, transaction logs, and mandates, then creates
exactly 3 mandates under user_id "demo-user" for the dashboard demo.

Usage (from the mandatecheck/ repo root):
    python backend/seed_demo.py
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db import SessionLocal  # noqa: E402
from app.models import Claim, Mandate, TransactionLog  # noqa: E402

DEMO_USER_ID = "demo-user"
FULL_DAY_WINDOW = {"start_hour": 0, "end_hour": 23}

MANDATES = [
    dict(
        agent_id="grocery-agent",
        agent_platform="chatgpt",
        agent_display_name="Grocery Agent",
        max_amount_per_txn=500.0,
        max_amount_per_window=2000.0,
        window_duration="7d",
        max_amount_total=10000.0,
        merchant_allowlist=["amazon", "bigbasket"],
        category_allowlist=["groceries", "household"],
        allowed_time_window=FULL_DAY_WINDOW,
        original_intent_text=(
            "Order groceries and household essentials from Amazon or "
            "BigBasket, up to 500 rupees per order."
        ),
        user_facing_summary=(
            "Groceries & household via Amazon/BigBasket — up to ₹500/order, "
            "₹2000/week, ₹10000 lifetime."
        ),
    ),
    dict(
        agent_id="food-delivery-agent",
        agent_platform="claude",
        agent_display_name="Food Delivery Agent",
        max_amount_per_txn=300.0,
        max_amount_per_window=1500.0,
        window_duration="7d",
        max_amount_total=5000.0,
        merchant_allowlist=["swiggy", "zomato"],
        category_allowlist=["food_delivery"],
        allowed_time_window={"start_hour": 10, "end_hour": 23},
        original_intent_text=(
            "Order food delivery from Swiggy or Zomato between 10am and "
            "11pm, up to 300 rupees per order."
        ),
        user_facing_summary=(
            "Food delivery via Swiggy/Zomato, 10am-11pm — up to ₹300/order, "
            "₹1500/week, ₹5000 lifetime."
        ),
    ),
    dict(
        agent_id="shopping-agent",
        agent_platform="chatgpt",
        agent_display_name="Shopping Agent",
        max_amount_per_txn=1000.0,
        max_amount_per_window=3000.0,
        window_duration="7d",
        max_amount_total=15000.0,
        merchant_allowlist=["flipkart"],
        category_allowlist=["electronics", "clothing"],
        allowed_time_window=FULL_DAY_WINDOW,
        original_intent_text=(
            "Order electronics and clothing from Flipkart, up to 1000 "
            "rupees per order."
        ),
        user_facing_summary=(
            "Electronics & clothing via Flipkart — up to ₹1000/order, "
            "₹3000/week, ₹15000 lifetime."
        ),
    ),
]


def main() -> None:
    db = SessionLocal()
    try:
        deleted_claims = db.query(Claim).delete()
        deleted_txns = db.query(TransactionLog).delete()
        deleted_mandates = db.query(Mandate).delete()
        db.commit()
        print(
            f"Cleared: {deleted_mandates} mandates, {deleted_txns} "
            f"transaction logs, {deleted_claims} claims."
        )

        now = datetime.now(timezone.utc)
        created = []
        for spec in MANDATES:
            mandate = Mandate(
                user_id=DEMO_USER_ID,
                expires_at=now + timedelta(days=365),
                status="active",
                **spec,
            )
            db.add(mandate)
            created.append(mandate)
        db.commit()
        for mandate in created:
            db.refresh(mandate)

        print(f"\nCreated 3 mandates under user_id={DEMO_USER_ID!r}:")
        for mandate in created:
            print(
                f"  - {mandate.agent_display_name!r} "
                f"({mandate.agent_platform}, mandate_id={mandate.mandate_id}) "
                f"merchants={mandate.merchant_allowlist} "
                f"categories={mandate.category_allowlist} "
                f"caps: {mandate.max_amount_per_txn}/txn, "
                f"{mandate.max_amount_per_window}/{mandate.window_duration}, "
                f"{mandate.max_amount_total} lifetime "
                f"window={mandate.allowed_time_window}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
