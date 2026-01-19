"""migrate_to_2upload_system - SAFE VERSION

Revision ID: 01ae25750241
Revises: add_hashed_password_to_admins
Create Date: 2026-01-19 17:57:51.500804

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '01ae25750241'
down_revision: Union[str, Sequence[str], None] = 'add_hashed_password_to_admins'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - SAFE VERSION: Only adds new columns, doesn't drop existing ones."""
    
    # ✅ ONLY ADD NEW COLUMNS - DON'T DROP EXISTING ONES
    op.add_column('existing_officers', sa.Column('passport_uploaded', sa.Boolean(), 
        nullable=True, server_default=sa.text('false'),
        comment='Passport photo uploaded status'))
    
    op.add_column('existing_officers', sa.Column('passport_path', sa.String(length=255), 
        nullable=True, comment='Passport photo path - JPG/PNG, 2MB max'))
    
    op.add_column('existing_officers', sa.Column('consolidated_pdf_uploaded', sa.Boolean(), 
        nullable=True, server_default=sa.text('false'),
        comment='Consolidated PDF uploaded status'))
    
    op.add_column('existing_officers', sa.Column('consolidated_pdf_path', sa.String(length=255), 
        nullable=True, comment='Consolidated PDF path - All 10 documents in one PDF, 10MB max'))
    
    # ✅ UPDATE COLUMN COMMENTS (KEEP EXISTING COLUMNS)
    op.alter_column('existing_officers', 'officer_id',
           existing_type=sa.VARCHAR(length=50),
           comment='Officer ID in NEW format: PREFIX/ALPHANUMERIC/INTAKE',
           existing_comment='Original officer ID from legacy system - NEW FORMAT: PREFIX/ALPHANUMERIC/INTAKE',
           existing_nullable=False)
    
    op.alter_column('existing_officers', 'category',
           existing_type=sa.VARCHAR(length=50),
           comment='Officer category: MCN (Marshal Core of Nigeria), MBT (Marshal Board of Trustees), MBC (Marshal Board of Committee)',
           existing_comment='Officer category: MCN (Marshal Core Nigeria), MBT (Marshal Board of Trustees), MBC (Marshal Board Committee)',
           existing_nullable=True)
    
    # ✅ ADD NEW INDEXES FOR NEW COLUMNS
    op.create_index('ix_existing_consolidated_uploaded', 'existing_officers', ['consolidated_pdf_uploaded'], unique=False)
    op.create_index('ix_existing_passport_uploaded', 'existing_officers', ['passport_uploaded'], unique=False)
    
    # ✅ UPDATE TABLE COMMENT (ADD INFO ABOUT 2-UPLOAD SYSTEM)
    op.execute("""
        COMMENT ON TABLE existing_officers IS 
        'Officers from legacy system with NEW date fields and dashboard tracking - UPDATED for 2-upload system'
    """)
    
    # ✅ DATA MIGRATION: Copy passport_photo to passport_path for existing records
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE existing_officers 
        SET passport_path = passport_photo,
            passport_uploaded = CASE 
                WHEN passport_photo IS NOT NULL THEN true 
                ELSE false 
            END
        WHERE passport_photo IS NOT NULL
    """))
    
    # ✅ SET DEFAULT VALUES FOR NULL COLUMNS
    connection.execute(sa.text("""
        UPDATE existing_officers 
        SET passport_uploaded = COALESCE(passport_uploaded, false),
            consolidated_pdf_uploaded = COALESCE(consolidated_pdf_uploaded, false)
    """))
    
    # ✅ MAKE NEW COLUMNS NOT NULL AFTER DATA POPULATION
    op.alter_column('existing_officers', 'passport_uploaded',
               existing_type=sa.Boolean(),
               nullable=False,
               existing_server_default=sa.text('false'))
    
    op.alter_column('existing_officers', 'consolidated_pdf_uploaded',
               existing_type=sa.Boolean(),
               nullable=False,
               existing_server_default=sa.text('false'))


def downgrade() -> None:
    """Downgrade schema - SAFELY remove only the new columns."""
    
    # ✅ SAFELY REMOVE ONLY THE COLUMNS WE ADDED
    op.drop_column('existing_officers', 'consolidated_pdf_path')
    op.drop_column('existing_officers', 'consolidated_pdf_uploaded')
    op.drop_column('existing_officers', 'passport_path')
    op.drop_column('existing_officers', 'passport_uploaded')
    
    # ✅ REMOVE NEW INDEXES
    op.drop_index('ix_existing_passport_uploaded', table_name='existing_officers')
    op.drop_index('ix_existing_consolidated_uploaded', table_name='existing_officers')
    
    # ✅ RESTORE COLUMN COMMENTS
    op.alter_column('existing_officers', 'category',
           existing_type=sa.VARCHAR(length=50),
           comment='Officer category: MCN (Marshal Core Nigeria), MBT (Marshal Board of Trustees), MBC (Marshal Board Committee)',
           existing_comment='Officer category: MCN (Marshal Core of Nigeria), MBT (Marshal Board of Trustees), MBC (Marshal Board of Committee)',
           existing_nullable=True)
    
    op.alter_column('existing_officers', 'officer_id',
           existing_type=sa.VARCHAR(length=50),
           comment='Original officer ID from legacy system - NEW FORMAT: PREFIX/ALPHANUMERIC/INTAKE',
           existing_comment='Officer ID in NEW format: PREFIX/ALPHANUMERIC/INTAKE',
           existing_nullable=False)
    
    # ✅ RESTORE TABLE COMMENT
    op.execute("""
        COMMENT ON TABLE existing_officers IS 
        'Officers from legacy system with NEW date fields and dashboard tracking'
    """)