"""add source to transaction_logs

Revision ID: 7a1c9e3f4d21
Revises: 9d4e2a7c1f3b
Create Date: 2026-07-23 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a1c9e3f4d21'
down_revision: Union[str, Sequence[str], None] = '9d4e2a7c1f3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'transaction_logs',
        sa.Column('source', sa.String(), nullable=False, server_default='manual'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('transaction_logs', 'source')
