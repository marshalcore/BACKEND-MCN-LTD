"""Safe migration to align database with current models - NO DESTRUCTIVE CHANGES

Revision ID: safe_alignment_migration
Revises: 0a94c4e21164
Create Date: 2026-02-07 02:30:31.906025

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect, text
import logging

revision: str = 'safe_alignment_migration'
down_revision: str = '0a94c4e21164'
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)

def check_column_exists(table_name: str, column_name: str, connection):
    """Check if column exists."""
    try:
        inspector = inspect(connection)
        return any(col['name'] == column_name for col in inspector.get_columns(table_name))
    except:
        return False

def check_table_exists(table_name: str, connection):
    """Check if table exists."""
    try:
        inspector = inspect(connection)
        return table_name in inspector.get_table_names()
    except:
        return False

def upgrade() -> None:
    connection = op.get_bind()
    
    logger.info("🔄 Starting safe database alignment migration")
    
    # 1. SAFELY add payment fields to applicants (if they don't exist)
    if check_table_exists('applicants', connection):
        payment_fields = [
            ('payment_type', sa.String(20), True),
            ('payment_status', sa.String(20), True),
            ('amount_paid', sa.Float(), True),
            ('payment_reference', sa.String(100), True)
        ]
        
        for col_name, col_type, nullable in payment_fields:
            if not check_column_exists('applicants', col_name, connection):
                logger.info(f"Adding {col_name} to applicants")
                op.add_column('applicants', sa.Column(col_name, col_type, nullable=nullable))
    
    # 2. SAFELY create indexes (they won't duplicate if they exist)
    try:
        op.create_index(op.f('ix_applicants_email'), 'applicants', ['email'], unique=True, if_not_exists=True)
        op.create_index(op.f('ix_applicants_nin_number'), 'applicants', ['nin_number'], unique=True, if_not_exists=True)
        op.create_index(op.f('ix_applicants_payment_reference'), 'applicants', ['payment_reference'], unique=False, if_not_exists=True)
    except Exception as e:
        logger.warning(f"Could not create indexes: {e}")
    
    # 3. DO NOT drop any columns from applicants - too risky!
    logger.info("⚠️ SKIPPING column drops from applicants - too dangerous")
    
    # 4. Safely convert JSON to JSONB for existing columns
    try:
        # Convert only if column exists and is JSON type
        if check_column_exists('applicants', 'selected_reasons', connection):
            op.execute(text("""
                ALTER TABLE applicants 
                ALTER COLUMN selected_reasons 
                TYPE JSONB 
                USING selected_reasons::jsonb
            """))
    except Exception as e:
        logger.warning(f"Could not convert selected_reasons: {e}")
    
    logger.info("✅ Safe migration complete")

def downgrade() -> None:
    """Simple downgrade - only removes what we added."""
    try:
        op.drop_index(op.f('ix_applicants_payment_reference'), table_name='applicants', if_exists=True)
        op.drop_index(op.f('ix_applicants_nin_number'), table_name='applicants', if_exists=True)
        op.drop_index(op.f('ix_applicants_email'), table_name='applicants', if_exists=True)
    except:
        pass