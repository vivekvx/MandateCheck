"""add razorpay_status and razorpay_order_id to transaction_logs

Revision ID: 9d4e2a7c1f3b
Revises: 8c1d4f6a2b30
Create Date: 2026-07-22 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d4e2a7c1f3b'
down_revision: Union[str, Sequence[str], None] = '8c1d4f6a2b30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'transaction_logs',
        sa.Column('razorpay_status', sa.String(), nullable=True),
    )
    op.add_column(
        'transaction_logs',
        sa.Column('razorpay_order_id', sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('transaction_logs', 'razorpay_order_id')
    op.drop_column('transaction_logs', 'razorpay_status')
