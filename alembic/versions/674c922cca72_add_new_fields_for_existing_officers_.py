"""Add new fields for existing officers: date_of_enlistment, date_of_promotion, category
Also clean up old document fields for 2-upload system

Revision ID: 674c922cca72
Revises: ae7187eb5fbc
Create Date: 2026-01-20 10:13:46.765780

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '674c922cca72'
down_revision: Union[str, Sequence[str], None] = 'ae7187eb5fbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    connection = op.get_bind()
    
    print("🚀 Starting migration: Cleanup old document fields and ensure new fields exist")
    
    # ==================== FIRST CHECK WHAT COLUMNS EXIST ====================
    
    # Check if date_of_enlistment already exists
    result = connection.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'existing_officers' 
        AND column_name = 'date_of_enlistment'
    """)).fetchone()
    
    if not result:
        print("❌ ERROR: date_of_enlistment column not found!")
        print("This column should already exist from previous migration.")
        print("Aborting migration to prevent data loss.")
        raise Exception("Critical column missing: date_of_enlistment")
    
    print("✅ Found date_of_enlistment column")
    
    # Check if date_of_promotion exists
    result = connection.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'existing_officers' 
        AND column_name = 'date_of_promotion'
    """)).fetchone()
    
    if not result:
        print("⚠️ date_of_promotion column not found - adding it")
        op.add_column('existing_officers', 
                     sa.Column('date_of_promotion', sa.Date(), nullable=True,
                              comment='Date of last promotion - OPTIONAL'))
        print("✅ Added date_of_promotion column")
    else:
        print("✅ Found date_of_promotion column")
    
    # Check if category exists
    result = connection.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'existing_officers' 
        AND column_name = 'category'
    """)).fetchone()
    
    if not result:
        print("⚠️ category column not found - adding it")
        op.add_column('existing_officers', 
                     sa.Column('category', sa.String(length=50), nullable=True,
                              comment='Officer category: MCN (Marshal Core of Nigeria), MBT (Marshal Board of Trustees), MBC (Marshal Board of Committee)'))
        print("✅ Added category column")
    else:
        print("✅ Found category column")
    
    # ==================== CLEANUP OLD DOCUMENT FIELDS (2-UPLOAD SYSTEM) ====================
    
    # Check and remove old document fields if they exist
    old_document_fields = [
        'passport_photo',  # Old name, should be passport_path
        'nin_slip',
        'ssce_certificate', 
        'birth_certificate',
        'letter_of_first_appointment',
        'promotion_letters',
        'legacy_application_pdf_path',
        'legacy_application_generated_at'
    ]
    
    for field in old_document_fields:
        result = connection.execute(sa.text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'existing_officers' 
            AND column_name = '{field}'
        """)).fetchone()
        
        if result:
            print(f"⚠️ Removing old document field: {field}")
            op.drop_column('existing_officers', field)
            print(f"✅ Removed {field}")
        else:
            print(f"✅ Old field {field} not found (already removed)")
    
    # ==================== ENSURE NEW 2-UPLOAD FIELDS EXIST ====================
    
    new_document_fields = [
        ('passport_uploaded', 'BOOLEAN', False, 'Passport photo uploaded status'),
        ('passport_path', 'VARCHAR(255)', None, 'Passport photo path - JPG/PNG, 2MB max'),
        ('consolidated_pdf_uploaded', 'BOOLEAN', False, 'Consolidated PDF uploaded status'),
        ('consolidated_pdf_path', 'VARCHAR(255)', None, 'Consolidated PDF path - All 10 documents in one PDF, 10MB max'),
        ('terms_pdf_path', 'VARCHAR(500)', None, 'Path to Terms & Conditions PDF'),
        ('registration_pdf_path', 'VARCHAR(500)', None, 'Path to Existing Officer Registration Form PDF'),
        ('terms_generated_at', 'TIMESTAMP WITH TIME ZONE', None, 'When Terms PDF was generated'),
        ('registration_generated_at', 'TIMESTAMP WITH TIME ZONE', None, 'When Registration PDF was generated')
    ]
    
    for field_name, field_type, default_value, comment in new_document_fields:
        result = connection.execute(sa.text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'existing_officers' 
            AND column_name = '{field_name}'
        """)).fetchone()
        
        if not result:
            print(f"⚠️ Adding new document field: {field_name}")
            
            if field_type == 'BOOLEAN':
                col = sa.Column(field_name, sa.Boolean(), nullable=True, default=default_value, comment=comment)
            elif field_type == 'VARCHAR(255)':
                col = sa.Column(field_name, sa.String(length=255), nullable=True, comment=comment)
            elif field_type == 'VARCHAR(500)':
                col = sa.Column(field_name, sa.String(length=500), nullable=True, comment=comment)
            elif field_type == 'TIMESTAMP WITH TIME ZONE':
                col = sa.Column(field_name, sa.DateTime(timezone=True), nullable=True, comment=comment)
            
            op.add_column('existing_officers', col)
            print(f"✅ Added {field_name}")
        else:
            print(f"✅ Field {field_name} already exists")
    
    # ==================== ENSURE INDEXES EXIST ====================
    
    # Check existing indexes
    result = connection.execute(sa.text("""
        SELECT indexname FROM pg_indexes 
        WHERE tablename = 'existing_officers'
    """)).fetchall()
    
    existing_indexes = [row[0] for row in result]
    
    # Create indexes if they don't exist
    indexes_to_create = [
        ('ix_existing_officer_id', 'officer_id'),
        ('ix_existing_officer_email', 'email'),
        ('ix_existing_officer_category', 'category'),
        ('ix_existing_officer_status', 'status'),
        ('ix_existing_officer_enlistment', 'date_of_enlistment'),
        ('ix_existing_passport_uploaded', 'passport_uploaded'),
        ('ix_existing_consolidated_uploaded', 'consolidated_pdf_uploaded')
    ]
    
    for index_name, column_name in indexes_to_create:
        if index_name not in existing_indexes:
            print(f"⚠️ Creating index: {index_name} on {column_name}")
            op.create_index(index_name, 'existing_officers', [column_name], unique=False)
            print(f"✅ Created index {index_name}")
        else:
            print(f"✅ Index {index_name} already exists")
    
    # ==================== UPDATE TABLE COMMENT ====================
    
    # Update table comment to reflect current state
    op.execute("""
        COMMENT ON TABLE existing_officers IS 
        'Table for existing officers - UPDATED for 2-upload system'
    """)
    
    print("✅ Migration completed successfully!")


def downgrade() -> None:
    """Downgrade schema - BE CAREFUL: This will remove new 2-upload fields!"""
    
    print("⚠️ WARNING: Downgrade will remove new 2-upload system fields!")
    print("Only proceed if you're sure you want to revert to old system.")
    
    connection = op.get_bind()
    
    # ==================== RESTORE OLD DOCUMENT FIELDS ====================
    
    # Add back old document fields with their original structure
    old_document_fields = [
        ('passport_photo', sa.String(length=255), 'Passport photo path - REQUIRED'),
        ('nin_slip', sa.String(length=255), 'NIN slip path - REQUIRED'),
        ('ssce_certificate', sa.String(length=255), 'SSCE certificate path - REQUIRED'),
        ('birth_certificate', sa.String(length=255), 'Birth certificate path - OPTIONAL'),
        ('letter_of_first_appointment', sa.String(length=255), 'First appointment letter - OPTIONAL'),
        ('promotion_letters', sa.String(length=255), 'Promotion letters - OPTIONAL'),
        ('legacy_application_pdf_path', sa.String(length=500), 'Path to Application Form PDF'),
        ('legacy_application_generated_at', postgresql.TIMESTAMP(timezone=True), 'When Application PDF was generated')
    ]
    
    for field_name, field_type, comment in old_document_fields:
        result = connection.execute(sa.text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'existing_officers' 
            AND column_name = '{field_name}'
        """)).fetchone()
        
        if not result:
            print(f"⚠️ Restoring old document field: {field_name}")
            op.add_column('existing_officers', sa.Column(field_name, field_type, nullable=True, comment=comment))
            print(f"✅ Restored {field_name}")
    
    # ==================== REMOVE NEW 2-UPLOAD FIELDS ====================
    
    new_document_fields = [
        'passport_uploaded',
        'passport_path',
        'consolidated_pdf_uploaded',
        'consolidated_pdf_path',
        'terms_pdf_path',
        'registration_pdf_path',
        'terms_generated_at',
        'registration_generated_at'
    ]
    
    for field_name in new_document_fields:
        result = connection.execute(sa.text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'existing_officers' 
            AND column_name = '{field_name}'
        """)).fetchone()
        
        if result:
            print(f"⚠️ Removing new 2-upload field: {field_name}")
            op.drop_column('existing_officers', field_name)
            print(f"✅ Removed {field_name}")
    
    # ==================== KEEP CRITICAL FIELDS ====================
    
    # DO NOT REMOVE these critical fields
    print("⚠️ Preserving critical fields: date_of_enlistment, date_of_promotion, category")
    
    # ==================== RESTORE OLD INDEXES ====================
    
    # Drop new indexes
    new_indexes = [
        'ix_existing_officer_id',
        'ix_existing_officer_email',
        'ix_existing_officer_category',
        'ix_existing_officer_status',
        'ix_existing_officer_enlistment',
        'ix_existing_passport_uploaded',
        'ix_existing_consolidated_uploaded'
    ]
    
    for index_name in new_indexes:
        try:
            op.drop_index(index_name, table_name='existing_officers')
            print(f"✅ Dropped index {index_name}")
        except:
            print(f"⚠️ Index {index_name} not found, skipping")
    
    # Create old style indexes
    op.create_index(op.f('ix_existing_officers_category'), 'existing_officers', ['category'], unique=False)
    op.create_index(op.f('ix_existing_officers_email'), 'existing_officers', ['email'], unique=True)
    op.create_index(op.f('ix_existing_officers_officer_id'), 'existing_officers', ['officer_id'], unique=True)
    op.create_index(op.f('ix_existing_officers_status'), 'existing_officers', ['status'], unique=False)
    
    # ==================== RESTORE TABLE COMMENT ====================
    
    op.execute("""
        COMMENT ON TABLE existing_officers IS 
        'Table for existing officers - UPDATED for 2-upload system with optional fields'
    """)
    
    print("✅ Downgrade completed (partial - critical fields preserved)")