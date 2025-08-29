"""Add payment tracking fields

Revision ID: 02e78ff9ca7a
Revises: 19cd77199422
Create Date: 2025-07-22 10:45:18.551322

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '02e78ff9ca7a'
down_revision = '19cd77199422'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('applicants', sa.Column('has_paid', sa.Boolean(), nullable=False))
    op.add_column('applicants', sa.Column('application_password', sa.String(), nullable=True))
    op.add_column('applicants', sa.Column('is_verified', sa.Boolean(), nullable=True))

def downgrade():
    op.drop_column('applicants', 'is_verified')
    op.drop_column('applicants', 'application_password')
    op.drop_column('applicants', 'has_paid')
