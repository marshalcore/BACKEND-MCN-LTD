"""add_missing_columns_to_admin_table

Revision ID: 11c88e3be873
Revises: 674c922cca72
Create Date: 2026-01-21 08:51:07.855992

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '11c88e3be873'
down_revision: Union[str, Sequence[str], None] = '674c922cca72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    inspector = inspect(op.get_bind())
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Upgrade schema - SAFELY add only Admin columns"""
    
    connection = op.get_bind()
    
    print("🚀 Starting SAFE migration: Adding missing columns to Admin table ONLY")
    
    # ==================== SAFELY ADD ADMIN COLUMNS ====================
    
    # 1. Add last_login column only if it doesn't exist
    if not check_column_exists('admins', 'last_login'):
        print("➡️ Adding last_login column to admins table")
        op.add_column('admins', 
            sa.Column('last_login', sa.DateTime(), nullable=True,
                     comment='Last login timestamp'))
        print("✅ Added last_login column")
    else:
        print("✅ last_login column already exists")
    
    # 2. Add created_at column only if it doesn't exist
    if not check_column_exists('admins', 'created_at'):
        print("➡️ Adding created_at column to admins table")
        op.add_column('admins', 
            sa.Column('created_at', sa.DateTime(), nullable=True,
                     comment='Record creation timestamp'))
        
        # Set default for existing rows
        connection.execute(sa.text("""
            UPDATE admins 
            SET created_at = CURRENT_TIMESTAMP 
            WHERE created_at IS NULL
        """))
        print("✅ Added created_at column with default values")
    else:
        print("✅ created_at column already exists")
    
    # 3. Add updated_at column only if it doesn't exist
    if not check_column_exists('admins', 'updated_at'):
        print("➡️ Adding updated_at column to admins table")
        op.add_column('admins', 
            sa.Column('updated_at', sa.DateTime(), nullable=True,
                     comment='Record last update timestamp'))
        
        # Set default for existing rows
        connection.execute(sa.text("""
            UPDATE admins 
            SET updated_at = CURRENT_TIMESTAMP 
            WHERE updated_at IS NULL
        """))
        print("✅ Added updated_at column with default values")
    else:
        print("✅ updated_at column already exists")
    
    # ==================== DO NOT TOUCH EXISTING_OFFICERS TABLE ====================
    
    print("\n⚠️ IMPORTANT: Skipping any changes to existing_officers table")
    print("✅ Preserving all indexes and table comment on existing_officers")
    print("✅ Migration only affects admins table")
    
    print("\n✅ SAFE migration completed successfully!")


def downgrade() -> None:
    """Downgrade schema - SAFELY remove only Admin columns if they exist"""
    
    print("⚠️ WARNING: Downgrading Admin table changes ONLY")
    
    connection = op.get_bind()
    
    # ==================== SAFELY REMOVE ADMIN COLUMNS ====================
    
    # 1. Remove updated_at column only if it exists
    if check_column_exists('admins', 'updated_at'):
        print("➡️ Removing updated_at column from admins table")
        op.drop_column('admins', 'updated_at')
        print("✅ Removed updated_at column")
    else:
        print("✅ updated_at column doesn't exist")
    
    # 2. Remove created_at column only if it exists
    if check_column_exists('admins', 'created_at'):
        print("➡️ Removing created_at column from admins table")
        op.drop_column('admins', 'created_at')
        print("✅ Removed created_at column")
    else:
        print("✅ created_at column doesn't exist")
    
    # 3. Remove last_login column only if it exists
    if check_column_exists('admins', 'last_login'):
        print("➡️ Removing last_login column from admins table")
        op.drop_column('admins', 'last_login')
        print("✅ Removed last_login column")
    else:
        print("✅ last_login column doesn't exist")
    
    # ==================== DO NOT TOUCH EXISTING_OFFICERS TABLE ====================
    
    print("\n⚠️ IMPORTANT: NOT touching existing_officers table during downgrade")
    print("✅ All indexes and table comment preserved")
    
    print("\n✅ SAFE downgrade completed!")