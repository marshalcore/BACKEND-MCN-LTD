"""Fix nullable constraints for optional fields

Revision ID: ae7187eb5fbc
Revises: fe9913a2d440
Create Date: 2026-01-19 20:44:33.720422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae7187eb5fbc'
down_revision: Union[str, Sequence[str], None] = 'fe9913a2d440'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Make optional fields nullable"""
    
    # First, update any existing NULL values to default values
    connection = op.get_bind()
    
    # Check if date_of_enlistment has any NULL values and fix them
    null_count = connection.execute(sa.text("""
        SELECT COUNT(*) FROM existing_officers WHERE date_of_enlistment IS NULL
    """)).scalar()
    
    if null_count > 0:
        connection.execute(sa.text("""
            UPDATE existing_officers 
            SET date_of_enlistment = '2000-01-01' 
            WHERE date_of_enlistment IS NULL
        """))
        print(f"✅ Fixed {null_count} NULL date_of_enlistment values")
    
    # Now make date_of_enlistment NOT NULL (CRITICAL from master prompt)
    op.alter_column('existing_officers', 'date_of_enlistment',
               existing_type=sa.DATE(),
               nullable=False)
    
    print("✅ Made date_of_enlistment NOT NULL (required field)")
    
    # Update column comment to reflect it's required
    op.alter_column('existing_officers', 'date_of_enlistment',
               existing_type=sa.DATE(),
               comment='Date officer enlisted - REQUIRED',
               existing_nullable=False)
    
    # ==================== MAKE OPTIONAL FIELDS NULLABLE ====================
    
    # Personal Information - These should be optional
    op.alter_column('existing_officers', 'place_of_birth',
               existing_type=sa.String(length=100),
               nullable=True)
    
    op.alter_column('existing_officers', 'nationality',
               existing_type=sa.String(length=50),
               nullable=True)
    
    op.alter_column('existing_officers', 'marital_status',
               existing_type=sa.String(length=20),
               nullable=True)
    
    print("✅ Made personal info fields nullable")
    
    # Contact Information - These should be optional
    op.alter_column('existing_officers', 'state_of_residence',
               existing_type=sa.String(length=50),
               nullable=True)
    
    op.alter_column('existing_officers', 'local_government_residence',
               existing_type=sa.String(length=50),
               nullable=True)
    
    op.alter_column('existing_officers', 'country_of_residence',
               existing_type=sa.String(length=50),
               nullable=True)
    
    print("✅ Made contact info fields nullable")
    
    # Origin Information - These should be optional
    op.alter_column('existing_officers', 'state_of_origin',
               existing_type=sa.String(length=50),
               nullable=True)
    
    op.alter_column('existing_officers', 'local_government_origin',
               existing_type=sa.String(length=50),
               nullable=True)
    
    print("✅ Made origin info fields nullable")
    
    # Professional Information - Position should be optional
    op.alter_column('existing_officers', 'position',
               existing_type=sa.String(length=100),
               nullable=True)
    
    print("✅ Made position field nullable")
    
    # ==================== FIX DOCUMENT UPLOAD FIELDS ====================
    
    # These should be nullable for new registrations
    op.alter_column('existing_officers', 'passport_uploaded',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    
    op.alter_column('existing_officers', 'consolidated_pdf_uploaded',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    
    print("✅ Made document upload fields nullable")
    
    # ==================== ADD INDEXES FOR 2-UPLOAD SYSTEM ====================
    
    # Check what indexes already exist
    result = connection.execute(sa.text("""
        SELECT indexname FROM pg_indexes 
        WHERE tablename = 'existing_officers'
    """)).fetchall()
    
    existing_indexes = [row[0] for row in result]
    
    # Add new indexes for the 2-upload system
    if 'ix_existing_consolidated_uploaded' not in existing_indexes:
        op.create_index('ix_existing_consolidated_uploaded', 'existing_officers', ['consolidated_pdf_uploaded'], unique=False)
    
    if 'ix_existing_passport_uploaded' not in existing_indexes:
        op.create_index('ix_existing_passport_uploaded', 'existing_officers', ['passport_uploaded'], unique=False)
    
    if 'ix_existing_officer_enlistment' not in existing_indexes:
        op.create_index('ix_existing_officer_enlistment', 'existing_officers', ['date_of_enlistment'], unique=False)
    
    print("✅ Added indexes for 2-upload system")
    
    # ==================== UPDATE TABLE COMMENT ====================
    
    op.execute("""
        COMMENT ON TABLE existing_officers IS 
        'Table for existing officers - UPDATED for 2-upload system with optional fields'
    """)
    
    print("✅ Migration completed successfully!")


def downgrade() -> None:
    """Downgrade schema - Restore NOT NULL constraints"""
    
    connection = op.get_bind()
    
    # First, set default values for any NULL values in optional fields
    connection.execute(sa.text("""
        UPDATE existing_officers 
        SET place_of_birth = COALESCE(place_of_birth, 'Not Specified'),
            nationality = COALESCE(nationality, 'Nigerian'),
            marital_status = COALESCE(marital_status, 'Not Specified'),
            state_of_residence = COALESCE(state_of_residence, 'Not Specified'),
            local_government_residence = COALESCE(local_government_residence, 'Not Specified'),
            country_of_residence = COALESCE(country_of_residence, 'Nigeria'),
            state_of_origin = COALESCE(state_of_origin, 'Not Specified'),
            local_government_origin = COALESCE(local_government_origin, 'Not Specified'),
            position = COALESCE(position, 'Not Specified'),
            passport_uploaded = COALESCE(passport_uploaded, false),
            consolidated_pdf_uploaded = COALESCE(consolidated_pdf_uploaded, false)
        WHERE place_of_birth IS NULL OR nationality IS NULL OR marital_status IS NULL 
           OR state_of_residence IS NULL OR local_government_residence IS NULL 
           OR country_of_residence IS NULL OR state_of_origin IS NULL 
           OR local_government_origin IS NULL OR position IS NULL
           OR passport_uploaded IS NULL OR consolidated_pdf_uploaded IS NULL
    """))
    
    # ==================== RESTORE NOT NULL CONSTRAINTS ====================
    
    # Personal Information
    op.alter_column('existing_officers', 'place_of_birth',
               existing_type=sa.String(length=100),
               nullable=False)
    
    op.alter_column('existing_officers', 'nationality',
               existing_type=sa.String(length=50),
               nullable=False)
    
    op.alter_column('existing_officers', 'marital_status',
               existing_type=sa.String(length=20),
               nullable=False)
    
    # Contact Information
    op.alter_column('existing_officers', 'state_of_residence',
               existing_type=sa.String(length=50),
               nullable=False)
    
    op.alter_column('existing_officers', 'local_government_residence',
               existing_type=sa.String(length=50),
               nullable=False)
    
    op.alter_column('existing_officers', 'country_of_residence',
               existing_type=sa.String(length=50),
               nullable=False)
    
    # Origin Information
    op.alter_column('existing_officers', 'state_of_origin',
               existing_type=sa.String(length=50),
               nullable=False)
    
    op.alter_column('existing_officers', 'local_government_origin',
               existing_type=sa.String(length=50),
               nullable=False)
    
    # Professional Information
    op.alter_column('existing_officers', 'position',
               existing_type=sa.String(length=100),
               nullable=False)
    
    # Document Upload Fields
    op.alter_column('existing_officers', 'passport_uploaded',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    
    op.alter_column('existing_officers', 'consolidated_pdf_uploaded',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    
    # Make date_of_enlistment nullable again (but keep existing values)
    op.alter_column('existing_officers', 'date_of_enlistment',
               existing_type=sa.DATE(),
               nullable=True)
    
    # Restore original comment
    op.alter_column('existing_officers', 'date_of_enlistment',
               existing_type=sa.DATE(),
               comment='Date officer enlisted',
               existing_nullable=True)
    
    # ==================== REMOVE NEW INDEXES ====================
    
    op.drop_index('ix_existing_officer_enlistment', table_name='existing_officers', if_exists=True)
    op.drop_index('ix_existing_passport_uploaded', table_name='existing_officers', if_exists=True)
    op.drop_index('ix_existing_consolidated_uploaded', table_name='existing_officers', if_exists=True)
    
    # ==================== RESTORE TABLE COMMENT ====================
    
    op.execute("""
        COMMENT ON TABLE existing_officers IS 
        'Officers from legacy system with NEW date fields and dashboard tracking - UPDATED for 2-upload system'
    """)
    
    print("✅ Downgrade completed - Restored original constraints")