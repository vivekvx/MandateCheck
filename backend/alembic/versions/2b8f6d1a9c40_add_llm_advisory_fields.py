"""add llm_review_flagged and llm_advisory_note to transaction_logs

Revision ID: 2b8f6d1a9c40
Revises: 7a1c9e3f4d21
Create Date: 2026-07-23 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b8f6d1a9c40'
down_revision: Union[str, Sequence[str], None] = '7a1c9e3f4d21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'transaction_logs',
        sa.Column('llm_review_flagged', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'transaction_logs',
        sa.Column('llm_advisory_note', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('transaction_logs', 'llm_advisory_note')
    op.drop_column('transaction_logs', 'llm_review_flagged')
