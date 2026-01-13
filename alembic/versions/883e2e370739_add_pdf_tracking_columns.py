"""add pdf tracking columns to all user tables - CORRECTED

Revision ID: 883e2e370739
Revises: d1668795832a
Create Date: 2026-01-13 13:57:16.639224

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '883e2e370739'
down_revision: Union[str, Sequence[str], None] = 'd1668795832a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add PDF tracking columns to applicants, officers, and existing_officers tables"""
    
    # Add columns to applicants table
    op.add_column('applicants',
        sa.Column('terms_pdf_path', sa.String(length=500), nullable=True, comment='Path to Terms & Conditions PDF')
    )
    op.add_column('applicants',
        sa.Column('application_pdf_path', sa.String(length=500), nullable=True, comment='Path to Application Form PDF')
    )
    op.add_column('applicants',
        sa.Column('terms_generated_at', sa.DateTime(timezone=True), nullable=True, comment='When Terms PDF was generated')
    )
    op.add_column('applicants',
        sa.Column('application_generated_at', sa.DateTime(timezone=True), nullable=True, comment='When Application PDF was generated')
    )
    
    # Add columns to officers table
    op.add_column('officers',
        sa.Column('terms_pdf_path', sa.String(length=500), nullable=True, comment='Path to Terms & Conditions PDF')
    )
    op.add_column('officers',
        sa.Column('application_pdf_path', sa.String(length=500), nullable=True, comment='Path to Application Form PDF')
    )
    op.add_column('officers',
        sa.Column('terms_generated_at', sa.DateTime(timezone=True), nullable=True, comment='When Terms PDF was generated')
    )
    op.add_column('officers',
        sa.Column('application_generated_at', sa.DateTime(timezone=True), nullable=True, comment='When Application PDF was generated')
    )
    
    # Add columns to existing_officers table
    op.add_column('existing_officers',
        sa.Column('terms_pdf_path', sa.String(length=500), nullable=True, comment='Path to Terms & Conditions PDF')
    )
    op.add_column('existing_officers',
        sa.Column('application_pdf_path', sa.String(length=500), nullable=True, comment='Path to Application Form PDF')
    )
    op.add_column('existing_officers',
        sa.Column('terms_generated_at', sa.DateTime(timezone=True), nullable=True, comment='When Terms PDF was generated')
    )
    op.add_column('existing_officers',
        sa.Column('application_generated_at', sa.DateTime(timezone=True), nullable=True, comment='When Application PDF was generated')
    )


def downgrade() -> None:
    """Remove PDF tracking columns from all tables"""
    
    # Drop columns from existing_officers table
    op.drop_column('existing_officers', 'application_generated_at')
    op.drop_column('existing_officers', 'terms_generated_at')
    op.drop_column('existing_officers', 'application_pdf_path')
    op.drop_column('existing_officers', 'terms_pdf_path')
    
    # Drop columns from officers table
    op.drop_column('officers', 'application_generated_at')
    op.drop_column('officers', 'terms_generated_at')
    op.drop_column('officers', 'application_pdf_path')
    op.drop_column('officers', 'terms_pdf_path')
    
    # Drop columns from applicants table
    op.drop_column('applicants', 'application_generated_at')
    op.drop_column('applicants', 'terms_generated_at')
    op.drop_column('applicants', 'application_pdf_path')
    op.drop_column('applicants', 'terms_pdf_path')