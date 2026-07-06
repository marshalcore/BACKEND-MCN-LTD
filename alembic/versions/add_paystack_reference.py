"""Add paystack_reference field to payments

Revision ID: add_paystack_reference
Revises: latest
Create Date: 2025-07-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_paystack_reference'
down_revision = None  # Update this to the latest migration
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('payments', sa.Column('paystack_reference', sa.String(), nullable=True, index=True))


def downgrade():
    op.drop_column('payments', 'paystack_reference')
