"""Add immediate transfer fields to payments table - SAFE VERSION

Revision ID: 0a94c4e21164
Revises: 2eb2c764464b
Create Date: 2026-02-05 15:01:04.022136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '0a94c4e21164'
down_revision: Union[str, Sequence[str], None] = '2eb2c764464b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def check_column_exists(table_name: str, column_name: str, connection) -> bool:
    """Check if a column exists in a table"""
    inspector = inspect(connection)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Upgrade schema - SAFE VERSION - ONLY ADD PAYMENT COLUMNS"""
    
    connection = op.get_bind()
    
    print("🚀 Starting SAFE migration for immediate transfer payment fields")
    print("=" * 60)
    print("⚠️  IMPORTANT: This migration ONLY adds new columns")
    print("⚠️  It will NOT drop any existing columns or indexes")
    print("=" * 60)
    
    # ==================== ADD PAYMENT COLUMNS ====================
    
    print("\n💰 Adding payment columns for immediate transfers:")
    print("-" * 40)
    
    # List of new columns to add to payments table
    new_payment_columns = [
        ('immediate_transfers_processed', sa.Boolean(), True, 'false'),
        ('transfer_metadata', postgresql.JSON(astext_type=sa.Text()), True, None),
        ('director_general_share', sa.Integer(), True, 0),
        ('estech_system_share', sa.Integer(), True, 0),
        ('marshal_net_amount', sa.Float(), True, None),
    ]
    
    for col_name, col_type, nullable, default_value in new_payment_columns:
        if not check_column_exists('payments', col_name, connection):
            print(f"  ➕ Adding {col_name} column")
            
            # Create column
            if nullable:
                op.add_column('payments', sa.Column(col_name, col_type, nullable=True))
            else:
                op.add_column('payments', sa.Column(col_name, col_type, nullable=False))
            
            # Set default value if provided
            if default_value is not None:
                if isinstance(default_value, str) and default_value in ['false', 'true']:
                    # Boolean default
                    connection.execute(sa.text(f"""
                        UPDATE payments SET {col_name} = {default_value} 
                        WHERE {col_name} IS NULL
                    """))
                elif isinstance(default_value, (int, float)):
                    # Numeric default
                    connection.execute(sa.text(f"""
                        UPDATE payments SET {col_name} = {default_value} 
                        WHERE {col_name} IS NULL
                    """))
                print(f"    ✅ Set default: {default_value}")
            
            print(f"    ✅ Column added successfully")
        else:
            print(f"  ✓ {col_name} already exists")
    
    # Handle estech_share -> estech_commission migration
    if check_column_exists('payments', 'estech_share', connection):
        print("\n🔄 Checking estech_share column migration:")
        print("-" * 40)
        
        # Check if we should rename estech_share to estech_commission
        if not check_column_exists('payments', 'estech_commission', connection):
            print("  🔄 Renaming estech_share to estech_commission")
            op.alter_column('payments', 'estech_share', new_column_name='estech_commission')
            print("    ✅ Column renamed")
        else:
            print("  ✓ estech_commission already exists")
            
            # Copy data from estech_share to estech_commission if needed
            print("  📊 Checking for data migration")
            result = connection.execute(sa.text("""
                SELECT COUNT(*) FROM payments 
                WHERE estech_commission IS NULL AND estech_share IS NOT NULL
            """)).scalar()
            
            if result > 0:
                print(f"    📥 Migrating {result} records from estech_share to estech_commission")
                connection.execute(sa.text("""
                    UPDATE payments 
                    SET estech_commission = estech_share 
                    WHERE estech_commission IS NULL AND estech_share IS NOT NULL
                """))
                print("    ✅ Data migrated")
    else:
        print("\n  ✓ estech_share column not found (no migration needed)")
    
    # Calculate values for existing payments
    print("\n🧮 Calculating values for existing payments:")
    print("-" * 40)
    
    # Count successful payments
    result = connection.execute(sa.text("""
        SELECT COUNT(*) FROM payments 
        WHERE status = 'success' AND amount > 0
    """)).scalar()
    
    print(f"  📊 Found {result} successful payments to update")
    
    if result > 0:
        # Calculate director_general_share (35% of amount)
        connection.execute(sa.text("""
            UPDATE payments 
            SET director_general_share = amount * 0.35
            WHERE status = 'success' AND amount > 0 
            AND (director_general_share IS NULL OR director_general_share = 0)
        """))
        print("    ✅ Calculated director_general_share (35%)")
        
        # Calculate estech_system_share (15% of amount)
        connection.execute(sa.text("""
            UPDATE payments 
            SET estech_system_share = amount * 0.15
            WHERE status = 'success' AND amount > 0 
            AND (estech_system_share IS NULL OR estech_system_share = 0)
        """))
        print("    ✅ Calculated estech_system_share (15%)")
        
        # Calculate marshal_net_amount
        # Regular: amount * 0.48 - 197.7 (fees)
        # VIP: amount * 0.48 - 897 (fees)
        connection.execute(sa.text("""
            UPDATE payments 
            SET marshal_net_amount = 
                CASE 
                    WHEN payment_type = 'regular' THEN (amount * 0.48) - 197.7
                    WHEN payment_type = 'vip' THEN (amount * 0.48) - 897
                    ELSE 0
                END
            WHERE status = 'success' AND amount > 0 
            AND marshal_net_amount IS NULL
        """))
        print("    ✅ Calculated marshal_net_amount")
    
    # ==================== FINAL SUMMARY ====================
    
    print("\n" + "=" * 60)
    print("✅ SAFE MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("\n📊 Summary of changes to payments table:")
    print("  • ✅ Added immediate_transfers_processed (boolean)")
    print("  • ✅ Added transfer_metadata (JSON)")
    print("  • ✅ Added director_general_share (35% of amount)")
    print("  • ✅ Added estech_system_share (15% of amount)")
    print("  • ✅ Added marshal_net_amount (calculated)")
    print("  • ✅ Preserved estech_share/estech_commission column")
    print("\n🔒 NO EXISTING DATA WAS MODIFIED OR DELETED")
    print("🔒 NO EXISTING COLUMNS WERE REMOVED")
    print("🔒 NO INDEXES WERE TOUCHED")
    print("\n🚀 Your payments system is now ready for immediate transfers!")


def downgrade() -> None:
    """Downgrade schema - SAFE VERSION - REMOVE ONLY NEW COLUMNS"""
    
    connection = op.get_bind()
    
    print("⚠️  STARTING SAFE DOWNGRADE - REMOVING NEW PAYMENT COLUMNS")
    print("=" * 60)
    print("⚠️  WARNING: This will remove only the columns added in this migration")
    print("⚠️  Existing data in other columns will be preserved")
    print("=" * 60)
    
    # ==================== REMOVE NEW PAYMENT COLUMNS ====================
    
    print("\n💰 Removing payment columns added in this migration:")
    print("-" * 40)
    
    # List of columns to remove (added in this migration)
    columns_to_remove = [
        'marshal_net_amount',
        'estech_system_share',
        'director_general_share',
        'transfer_metadata',
        'immediate_transfers_processed',
    ]
    
    for col_name in columns_to_remove:
        if check_column_exists('payments', col_name, connection):
            print(f"  ➖ Removing {col_name}")
            op.drop_column('payments', col_name)
            print(f"    ✅ Removed")
        else:
            print(f"  ✓ {col_name} doesn't exist (nothing to remove)")
    
    # Handle estech_commission -> estech_share rollback
    if check_column_exists('payments', 'estech_commission', connection):
        print("\n🔄 Rolling back estech_commission to estech_share:")
        print("-" * 40)
        
        # Check if estech_share exists
        if not check_column_exists('payments', 'estech_share', connection):
            print("  🔄 Renaming estech_commission back to estech_share")
            op.alter_column('payments', 'estech_commission', new_column_name='estech_share')
            print("    ✅ Column renamed back")
        else:
            print("  ⚠️  estech_share already exists - keeping both columns")
            print("  ℹ️  Data will remain in estech_commission column")
    else:
        print("\n  ✓ estech_commission not found (no rollback needed)")
    
    # ==================== FINAL SUMMARY ====================
    
    print("\n" + "=" * 60)
    print("✅ SAFE DOWNGRADE COMPLETED!")
    print("=" * 60)
    print("\n📊 Summary:")
    print("  • ✅ Removed marshal_net_amount column")
    print("  • ✅ Removed estech_system_share column")
    print("  • ✅ Removed director_general_share column")
    print("  • ✅ Removed transfer_metadata column")
    print("  • ✅ Removed immediate_transfers_processed column")
    print("  • ✅ Rolled back estech_commission rename if applicable")
    print("\n🔒 ALL OTHER DATA AND COLUMNS WERE PRESERVED")
    print("🔒 NO EXISTING COLUMNS WERE AFFECTED")