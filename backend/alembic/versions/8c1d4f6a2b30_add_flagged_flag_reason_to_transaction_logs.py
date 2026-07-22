"""add flagged and flag_reason to transaction_logs

Revision ID: 8c1d4f6a2b30
Revises: 3aba7060b919
Create Date: 2026-07-21 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c1d4f6a2b30'
down_revision: Union[str, Sequence[str], None] = '3aba7060b919'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'transaction_logs',
        sa.Column('flagged', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'transaction_logs',
        sa.Column('flag_reason', sa.String(), nullable=True),
    )
    op.alter_column('transaction_logs', 'flagged', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('transaction_logs', 'flag_reason')
    op.drop_column('transaction_logs', 'flagged')
