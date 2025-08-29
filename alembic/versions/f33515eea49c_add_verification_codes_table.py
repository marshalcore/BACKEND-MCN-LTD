"""Add verification_codes table

Revision ID: f33515eea49c
Revises: 84033dc0cc03
Create Date: 2025-07-29 23:34:05.849566
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f33515eea49c'
down_revision: Union[str, Sequence[str], None] = '84033dc0cc03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'verification_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('code', sa.String(length=6), nullable=False),
        sa.Column('purpose', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('verification_codes')
