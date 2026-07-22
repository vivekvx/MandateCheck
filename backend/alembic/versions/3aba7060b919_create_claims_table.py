"""create claims table

Revision ID: 3aba7060b919
Revises: 2f2b9d2f1e58
Create Date: 2026-07-21 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3aba7060b919'
down_revision: Union[str, Sequence[str], None] = '2f2b9d2f1e58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('claims',
    sa.Column('claim_id', sa.UUID(), nullable=False),
    sa.Column('transaction_id', sa.UUID(), nullable=False),
    sa.Column('claim_reason', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('recommendation', sa.String(), nullable=True),
    sa.Column('recommendation_basis', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['transaction_id'], ['transaction_logs.transaction_id'], ),
    sa.PrimaryKeyConstraint('claim_id')
    )
    op.create_index(op.f('ix_claims_transaction_id'), 'claims', ['transaction_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_claims_transaction_id'), table_name='claims')
    op.drop_table('claims')
