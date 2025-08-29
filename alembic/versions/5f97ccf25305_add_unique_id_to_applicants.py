"""add_unique_id_to_applicants

Revision ID: 5f97ccf25305
Revises: 8ff01ac2c8a2
Create Date: 2025-08-13 20:28:18.293521

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5f97ccf25305'
down_revision = '8ff01ac2c8a2'
branch_labels = None
depends_on = None


def upgrade():
    # Add the unique_id column (nullable at first)
    op.add_column(
        'applicants',
        sa.Column('unique_id', sa.String(length=50), nullable=True)
    )
    
    # Create a unique constraint
    op.create_unique_constraint(
        'uq_applicants_unique_id',
        'applicants',
        ['unique_id']
    )
    
    # Optional: Populate existing records with default values
    # op.execute("UPDATE applicants SET unique_id = id::text WHERE unique_id IS NULL")


def downgrade():
    # Remove the unique constraint first
    op.drop_constraint(
        'uq_applicants_unique_id',
        'applicants',
        type_='unique'
    )
    
    # Remove the column
    op.drop_column('applicants', 'unique_id')