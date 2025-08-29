"""fix_missing_passport_column

Revision ID: 6f79e0848f71
Revises: d40af2d206fa
Create Date: 2025-08-03 17:56:35.418551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f79e0848f71'
down_revision: Union[str, Sequence[str], None] = 'd40af2d206fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('officers', 
        sa.Column('passport', 
            sa.String(length=255), 
            nullable=True,
            comment='Path to officer passport photo'
        )
    )

def downgrade():
    op.drop_column('officers', 'passport')