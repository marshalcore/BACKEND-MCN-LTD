"""simplify_application_and_add_reasons

Revision ID: 2eb2c764464b
Revises: 11c88e3be873
Create Date: 2026-02-05 13:44:33.318473

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect  # ADD THIS IMPORT

# revision identifiers, used by Alembic.
revision: str = '2eb2c764464b'
down_revision: Union[str, Sequence[str], None] = '11c88e3be873'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def check_column_exists(table_name: str, column_name: str, connection) -> bool:
    """Check if a column exists in a table"""
    inspector = inspect(connection)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def check_table_exists(table_name: str, connection) -> bool:
    """Check if a table exists"""
    inspector = inspect(connection)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Upgrade schema - SAFE VERSION"""
    
    connection = op.get_bind()
    
    print("🚀 Starting SAFE migration for application simplification")
    print("=" * 60)
    
    # ==================== CREATE NEW TABLES ====================
    
    # 1. Create immediate_transfers table only if it doesn't exist
    if not check_table_exists('immediate_transfers', connection):
        print("➡️ Creating immediate_transfers table")
        op.create_table('immediate_transfers',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('payment_reference', sa.String(), nullable=False),
            sa.Column('recipient_type', sa.String(), nullable=False),
            sa.Column('recipient_account', sa.String(), nullable=False),
            sa.Column('recipient_bank', sa.String(), nullable=False),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('transfer_reference', sa.String(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('paystack_response', sa.JSON(), nullable=True),
            sa.Column('paystack_transfer_code', sa.String(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('transferred_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('retry_count', sa.Integer(), nullable=True),
            sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_immediate_transfers_payment_reference'), 'immediate_transfers', ['payment_reference'], unique=False)
        op.create_index(op.f('ix_immediate_transfers_transfer_reference'), 'immediate_transfers', ['transfer_reference'], unique=False)
        print("✅ Created immediate_transfers table")
    else:
        print("✅ immediate_transfers table already exists")
    
    # ==================== ADD NEW COLUMNS TO APPLICANTS ====================
    
    print("\n📋 Adding new columns to applicants table:")
    print("-" * 40)
    
    new_applicant_columns = [
        ('lga', sa.String(length=50), False, 'Not specified'),
        ('address', sa.Text(), False, 'Not provided'),
        ('application_tier', sa.String(length=20), False, 'regular'),
        ('selected_reasons', postgresql.JSON(astext_type=sa.Text()), False, '[]'),
        ('additional_details', sa.Text(), True, None),
        ('segmentation_tags', postgresql.JSON(astext_type=sa.Text()), True, None),
        ('assigned_programs', postgresql.JSON(astext_type=sa.Text()), True, None),
    ]
    
    for col_name, col_type, nullable, default_value in new_applicant_columns:
        if not check_column_exists('applicants', col_name, connection):
            print(f"  ➕ Adding {col_name} column")
            op.add_column('applicants', sa.Column(col_name, col_type, nullable=nullable))
            
            # Set default value for non-nullable columns
            if not nullable and default_value:
                if default_value == '[]':
                    connection.execute(sa.text(f"""
                        UPDATE applicants SET {col_name} = '{default_value}'::json 
                        WHERE {col_name} IS NULL
                    """))
                else:
                    connection.execute(sa.text(f"""
                        UPDATE applicants SET {col_name} = '{default_value}' 
                        WHERE {col_name} IS NULL
                    """))
                print(f"    ✅ Set default: {default_value}")
        else:
            print(f"  ✓ {col_name} already exists")
    
    # ==================== MAKE OLD COLUMNS NULLABLE (SAFE) ====================
    
    print("\n🔄 Making old columns nullable (preserving data):")
    print("-" * 40)
    
    old_columns_to_nullable = [
        'agree_to_return_properties',
        'local_government_origin',
        'state_of_origin',
        'category',
        'additional_skills',
        'residential_address',
        'surname',
        'ssce_certificate',
        'first_name',
        'local_government_residence',
        'religion',
        'agree_to_join',
        'account_number',
        'place_of_birth',
        'gender',
        'bank_name',
        'design_rating',
        'country_of_residence',
        'marital_status',
        'mobile_number',
        'do_you_smoke',
        'agree_to_abide_rules',
        'higher_education_degree',
        'nationality',
        'other_name'
    ]
    
    for col_name in old_columns_to_nullable:
        if check_column_exists('applicants', col_name, connection):
            # Check current nullability
            inspector = inspect(connection)
            columns = inspector.get_columns('applicants')
            col_info = next((col for col in columns if col['name'] == col_name), None)
            
            if col_info and not col_info['nullable']:
                print(f"  🔄 Making {col_name} nullable")
                op.alter_column('applicants', col_name, nullable=True)
                print(f"    ✅ Made nullable")
            else:
                print(f"  ✓ {col_name} already nullable")
        else:
            print(f"  ⚠️ {col_name} not found (skipping)")
    
    # ==================== PRESERVE EXISTING_OFFICERS TABLE ====================
    
    print("\n🛡️ Preserving existing_officers table:")
    print("-" * 40)
    
    # DO NOT remove indexes or table comment
    print("  ✅ All indexes preserved")
    print("  ✅ Table comment preserved")
    print("  ✅ No changes made to existing_officers table")
    
    # ==================== ADD PAYMENT COLUMNS ====================
    
    print("\n💰 Adding payment columns:")
    print("-" * 40)
    
    new_payment_columns = [
        ('immediate_transfers_processed', sa.Boolean(), True, 'false'),
        ('transfer_metadata', sa.JSON(), True, None),
        ('director_general_share', sa.Integer(), True, None),
        ('estech_system_share', sa.Integer(), True, None),
        ('marshal_net_amount', sa.Float(), True, None),
        ('estech_commission', sa.Integer(), True, None),
    ]
    
    for col_name, col_type, nullable, default_value in new_payment_columns:
        if not check_column_exists('payments', col_name, connection):
            print(f"  ➕ Adding {col_name} column")
            op.add_column('payments', sa.Column(col_name, col_type, nullable=nullable))
            
            # Set default for boolean
            if col_name == 'immediate_transfers_processed' and default_value:
                connection.execute(sa.text(f"""
                    UPDATE payments SET {col_name} = {default_value} 
                    WHERE {col_name} IS NULL
                """))
                print(f"    ✅ Set default: {default_value}")
        else:
            print(f"  ✓ {col_name} already exists")
    
    # Handle estech_share -> estech_commission migration
    if check_column_exists('payments', 'estech_share', connection):
        print("  🔄 Migrating estech_share to estech_commission")
        connection.execute(sa.text("""
            UPDATE payments 
            SET estech_commission = estech_share 
            WHERE estech_commission IS NULL AND estech_share IS NOT NULL
        """))
        print("    ✅ Data migrated")
    
    # ==================== ADD PRE_APPLICANT COLUMNS ====================
    
    print("\n👤 Adding pre_applicant columns:")
    print("-" * 40)
    
    new_pre_applicant_columns = [
        ('selected_tier', sa.String(length=20), True, None),
        ('tier_selected_at', sa.DateTime(), True, None),
        ('privacy_accepted', sa.Boolean(), True, 'false'),
        ('privacy_accepted_at', sa.DateTime(), True, None),
    ]
    
    for col_name, col_type, nullable, default_value in new_pre_applicant_columns:
        if not check_column_exists('pre_applicants', col_name, connection):
            print(f"  ➕ Adding {col_name} column")
            op.add_column('pre_applicants', sa.Column(col_name, col_type, nullable=nullable))
            
            if col_name == 'privacy_accepted' and default_value:
                connection.execute(sa.text(f"""
                    UPDATE pre_applicants SET {col_name} = {default_value} 
                    WHERE {col_name} IS NULL
                """))
                print(f"    ✅ Set default: {default_value}")
        else:
            print(f"  ✓ {col_name} already exists")
    
    # ==================== FINAL SUMMARY ====================
    
    print("\n" + "=" * 60)
    print("✅ SAFE MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("\n📊 Summary of changes:")
    print("  • ✅ Created immediate_transfers table (if not exists)")
    print("  • ✅ Added new columns to applicants")
    print("  • ✅ Made old columns nullable (data preserved)")
    print("  • ✅ Preserved existing_officers table (no changes)")
    print("  • ✅ Added payment columns for split transactions")
    print("  • ✅ Added pre_applicant columns for tier & privacy")
    print("  • ✅ All existing data preserved")
    print("\n🚀 Your application is now ready for the new simplified form!")


def downgrade() -> None:
    """Downgrade schema - SAFE VERSION"""
    
    connection = op.get_bind()
    
    print("⚠️  STARTING SAFE DOWNGRADE")
    print("=" * 60)
    print("⚠️  WARNING: This will remove new columns but preserve existing data")
    print("=" * 60)
    
    # ==================== REMOVE PRE_APPLICANT COLUMNS ====================
    
    print("\n👤 Removing pre_applicant columns:")
    print("-" * 40)
    
    columns_to_remove = [
        'privacy_accepted_at',
        'privacy_accepted',
        'tier_selected_at',
        'selected_tier',
    ]
    
    for col_name in columns_to_remove:
        if check_column_exists('pre_applicants', col_name, connection):
            print(f"  ➖ Removing {col_name}")
            op.drop_column('pre_applicants', col_name)
            print(f"    ✅ Removed")
        else:
            print(f"  ✓ {col_name} doesn't exist")
    
    # ==================== RESTORE PAYMENT COLUMNS ====================
    
    print("\n💰 Restoring payment columns:")
    print("-" * 40)
    
    # Remove new columns
    new_columns_to_remove = [
        'estech_commission',
        'marshal_net_amount',
        'estech_system_share',
        'director_general_share',
        'transfer_metadata',
        'immediate_transfers_processed',
    ]
    
    for col_name in new_columns_to_remove:
        if check_column_exists('payments', col_name, connection):
            print(f"  ➖ Removing {col_name}")
            op.drop_column('payments', col_name)
            print(f"    ✅ Removed")
        else:
            print(f"  ✓ {col_name} doesn't exist")
    
    # Ensure estech_share exists
    if not check_column_exists('payments', 'estech_share', connection):
        print("  ➕ Restoring estech_share column")
        op.add_column('payments', sa.Column('estech_share', sa.Integer(), nullable=True))
        print("    ✅ Restored")
    
    # ==================== RESTORE APPLICANT COLUMNS ====================
    
    print("\n📋 Restoring applicant columns:")
    print("-" * 40)
    
    # Remove new columns
    new_app_columns_to_remove = [
        'assigned_programs',
        'segmentation_tags',
        'additional_details',
        'selected_reasons',
        'application_tier',
        'address',
        'lga',
    ]
    
    for col_name in new_app_columns_to_remove:
        if check_column_exists('applicants', col_name, connection):
            print(f"  ➖ Removing {col_name}")
            op.drop_column('applicants', col_name)
            print(f"    ✅ Removed")
        else:
            print(f"  ✓ {col_name} doesn't exist")
    
    # Make old columns NOT NULLABLE again (with safe defaults)
    print("\n🔄 Making old columns NOT NULLABLE:")
    print("-" * 40)
    
    old_columns_to_restore = [
        ('other_name', 'Not provided'),
        ('nationality', 'Nigerian'),
        ('higher_education_degree', 'Not provided'),
        ('agree_to_abide_rules', 'true'),
        ('do_you_smoke', 'false'),
        ('mobile_number', 'Not provided'),
        ('marital_status', 'Single'),
        ('country_of_residence', 'Nigeria'),
        ('design_rating', '5'),
        ('bank_name', 'Not provided'),
        ('gender', 'Male'),
        ('place_of_birth', 'Not provided'),
        ('account_number', 'Not provided'),
        ('agree_to_join', 'true'),
        ('religion', 'Christian'),
        ('local_government_residence', 'Not specified'),
        ('first_name', 'Not provided'),
        ('ssce_certificate', 'Not provided'),
        ('surname', 'Not provided'),
        ('residential_address', 'Not provided'),
        ('additional_skills', 'None'),
        ('category', 'General'),
        ('state_of_origin', 'Not specified'),
        ('local_government_origin', 'Not specified'),
        ('agree_to_return_properties', 'true'),
    ]
    
    for col_name, default_value in old_columns_to_restore:
        if check_column_exists('applicants', col_name, connection):
            # First, fill NULL values with defaults
            print(f"  🔄 Checking {col_name} for NULL values")
            
            result = connection.execute(sa.text(f"""
                SELECT COUNT(*) FROM applicants WHERE {col_name} IS NULL
            """)).scalar()
            
            if result > 0:
                print(f"    ⚠️  Found {result} NULL values, setting to: {default_value}")
                
                if default_value in ['true', 'false']:
                    connection.execute(sa.text(f"""
                        UPDATE applicants SET {col_name} = {default_value} 
                        WHERE {col_name} IS NULL
                    """))
                elif default_value.isdigit():
                    connection.execute(sa.text(f"""
                        UPDATE applicants SET {col_name} = {default_value} 
                        WHERE {col_name} IS NULL
                    """))
                else:
                    connection.execute(sa.text(f"""
                        UPDATE applicants SET {col_name} = '{default_value}' 
                        WHERE {col_name} IS NULL
                    """))
            
            # Now make NOT NULLABLE
            print(f"    🔒 Making {col_name} NOT NULLABLE")
            op.alter_column('applicants', col_name, nullable=False)
            print(f"    ✅ Restored")
        else:
            print(f"  ⚠️  {col_name} not found (skipping)")
    
    # ==================== DROP IMMEDIATE_TRANSFERS TABLE ====================
    
    print("\n🗑️  Dropping immediate_transfers table:")
    print("-" * 40)
    
    if check_table_exists('immediate_transfers', connection):
        print("  ➖ Dropping immediate_transfers table")
        
        # Drop indexes first
        try:
            op.drop_index(op.f('ix_immediate_transfers_transfer_reference'), table_name='immediate_transfers')
            print("    ✅ Dropped transfer_reference index")
        except:
            pass
        
        try:
            op.drop_index(op.f('ix_immediate_transfers_payment_reference'), table_name='immediate_transfers')
            print("    ✅ Dropped payment_reference index")
        except:
            pass
        
        # Drop table
        op.drop_table('immediate_transfers')
        print("    ✅ Dropped table")
    else:
        print("  ✓ Table doesn't exist")
    
    # ==================== FINAL SUMMARY ====================
    
    print("\n" + "=" * 60)
    print("✅ SAFE DOWNGRADE COMPLETED!")
    print("=" * 60)
    print("\n📊 Summary:")
    print("  • ✅ Removed new columns from pre_applicants")
    print("  • ✅ Restored payment columns")
    print("  • ✅ Removed new applicant columns")
    print("  • ✅ Restored old columns to NOT NULLABLE")
    print("  • ✅ Dropped immediate_transfers table")
    print("\n⚠️  Note: Default values were set for NULL data")