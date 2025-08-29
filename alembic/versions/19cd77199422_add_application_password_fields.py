"""Add application password fields

Revision ID: 19cd77199422
Revises: 
Create Date: 2025-07-22 04:52:41.238171
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision = '19cd77199422'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('applicants',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('marital_status', sa.String(), nullable=False),
        sa.Column('nin_number', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('bank_name', sa.String(), nullable=False),
        sa.Column('account_number', sa.String(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('surname', sa.String(), nullable=False),
        sa.Column('other_name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('mobile_number', sa.String(), nullable=False),
        sa.Column('phone_number', sa.String(), nullable=False),
        sa.Column('gender', sa.String(), nullable=False),
        sa.Column('nationality', sa.String(), nullable=False),
        sa.Column('country_of_residence', sa.String(), nullable=False),
        sa.Column('state_of_origin', sa.String(), nullable=False),
        sa.Column('state_of_residence', sa.String(), nullable=False),
        sa.Column('residential_address', sa.String(), nullable=False),
        sa.Column('local_government_residence', sa.String(), nullable=False),
        sa.Column('local_government_origin', sa.String(), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=False),
        sa.Column('religion', sa.String(), nullable=False),
        sa.Column('place_of_birth', sa.String(), nullable=False),
        sa.Column('passport_photo', sa.String(), nullable=False),
        sa.Column('nin_slip', sa.String(), nullable=False),
        sa.Column('ssce_certificate', sa.String(), nullable=False),
        sa.Column('higher_education_degree', sa.String(), nullable=False),
        sa.Column('do_you_smoke', sa.Boolean(), nullable=False),
        sa.Column('agree_to_join', sa.Boolean(), nullable=False),
        sa.Column('agree_to_abide_rules', sa.Boolean(), nullable=False),
        sa.Column('agree_to_return_properties', sa.Boolean(), nullable=False),
        sa.Column('additional_skills', sa.String(), nullable=False),
        sa.Column('design_rating', sa.Integer(), nullable=False),
        sa.Column('application_password', sa.String(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_applicants_id'), 'applicants', ['id'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_applicants_id'), table_name='applicants')
    op.drop_table('applicants')
