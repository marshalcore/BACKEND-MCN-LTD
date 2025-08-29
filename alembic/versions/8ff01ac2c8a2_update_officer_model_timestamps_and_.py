"""update_officer_model_timestamps_and_rank_position

Revision ID: 8ff01ac2c8a2
Revises: f3165f415aae
Create Date: 2025-08-10 00:49:01.626872

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8ff01ac2c8a2'
down_revision: Union[str, Sequence[str], None] = 'f3165f415aae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Add new columns
    op.add_column('officers', sa.Column('rank', sa.String(length=50), nullable=True))
    op.add_column('officers', sa.Column('position', sa.String(length=100), nullable=True))
    
    # First set default values for any NULL updated_at records
    op.execute("UPDATE officers SET updated_at = created_at WHERE updated_at IS NULL")
    
    # Then modify timestamp columns
    op.alter_column('officers', 'last_login',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=True,
                   server_default=None)
    op.alter_column('officers', 'created_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=sa.text('now()'))
    op.alter_column('officers', 'updated_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=False,
                   server_default=sa.text('now()'))

def downgrade():
    # Reverse the changes
    op.drop_column('officers', 'position')
    op.drop_column('officers', 'rank')
    
    # Revert timestamp changes
    op.alter_column('officers', 'last_login',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=True)
    op.alter_column('officers', 'created_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=True)
    op.alter_column('officers', 'updated_at',
                   existing_type=sa.DateTime(timezone=True),
                   nullable=True)