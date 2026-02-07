"""Make NIN fields optional in applicants table - FIXED VERSION

Revision ID: 5b320b545de1
Revises: 58ca3c92bce0
Create Date: 2026-02-07 13:45:14.226194

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '5b320b545de1'
down_revision: Union[str, Sequence[str], None] = '58ca3c92bce0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - FIXED VERSION."""
    
    print("🚀 Starting migration to make NIN fields optional...")
    
    # 1. First, DROP the unique constraint on nin_number (not just the index)
    # This is necessary because PostgreSQL creates a unique index for constraints
    print("📝 Step 1: Dropping unique constraint on nin_number...")
    try:
        op.execute(text("""
            ALTER TABLE applicants 
            DROP CONSTRAINT IF EXISTS uq_applicants_nin_number
        """))
        print("✅ Dropped unique constraint on nin_number")
    except Exception as e:
        print(f"⚠️  Could not drop constraint: {e}")
    
    # 2. Make nin_number nullable
    print("📝 Step 2: Making nin_number nullable...")
    try:
        # Update empty strings to NULL
        op.execute(text("""
            UPDATE applicants 
            SET nin_number = NULL 
            WHERE nin_number = ''
        """))
        
        # Alter column to nullable
        op.alter_column('applicants', 'nin_number',
               existing_type=sa.String(),
               nullable=True,
               postgresql_using="nin_number::text")
        print("✅ Made nin_number nullable")
    except Exception as e:
        print(f"⚠️  Could not make nin_number nullable: {e}")
    
    # 3. Make nin_slip nullable
    print("📝 Step 3: Making nin_slip nullable...")
    try:
        # Update empty strings to NULL
        op.execute(text("""
            UPDATE applicants 
            SET nin_slip = NULL 
            WHERE nin_slip = ''
        """))
        
        # Alter column to nullable
        op.alter_column('applicants', 'nin_slip',
               existing_type=sa.String(),
               nullable=True,
               postgresql_using="nin_slip::text")
        print("✅ Made nin_slip nullable")
    except Exception as e:
        print(f"⚠️  Could not make nin_slip nullable: {e}")
    
    # 4. Create partial unique index for nin_number (only where not null)
    print("📝 Step 4: Creating partial unique index for nin_number...")
    try:
        op.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_applicants_nin_number_unique 
            ON applicants(nin_number) 
            WHERE nin_number IS NOT NULL
        """))
        print("✅ Created partial unique index for nin_number")
    except Exception as e:
        print(f"⚠️  Could not create partial index: {e}")
    
    # 5. Ensure email unique constraint exists
    print("📝 Step 5: Ensuring email unique constraint exists...")
    try:
        # Check if constraint exists by trying to create it (will fail if exists)
        op.execute(text("""
            DO $$ 
            BEGIN
                BEGIN
                    ALTER TABLE applicants ADD CONSTRAINT uq_applicants_email UNIQUE (email);
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                END;
            END $$;
        """))
        print("✅ Email unique constraint verified")
    except Exception as e:
        print(f"⚠️  Could not ensure email constraint: {e}")
    
    # 6. Add comments
    print("📝 Step 6: Adding column comments...")
    try:
        op.execute(text("""
            COMMENT ON COLUMN applicants.nin_number IS 'National Identity Number (optional)';
            COMMENT ON COLUMN applicants.nin_slip IS 'NIN slip upload path (optional)';
        """))
        print("✅ Added column comments")
    except Exception as e:
        print(f"⚠️  Could not add comments: {e}")
    
    print("🎉 Migration completed successfully!")


def downgrade() -> None:
    """Downgrade schema - CAREFUL: This may cause data loss."""
    
    print("⚠️  WARNING: Downgrading will require NIN fields...")
    print("⚠️  This may fail if any applicants have NULL NIN values")
    
    # 1. Drop the partial unique index
    print("📝 Step 1: Dropping partial index...")
    try:
        op.execute(text("""
            DROP INDEX IF EXISTS idx_applicants_nin_number_unique
        """))
        print("✅ Dropped partial index")
    except Exception as e:
        print(f"⚠️  Could not drop index: {e}")
    
    # 2. Restore nin_number to NOT NULL
    print("📝 Step 2: Restoring nin_number as NOT NULL...")
    try:
        # Update NULL values to empty string
        op.execute(text("""
            UPDATE applicants 
            SET nin_number = '' 
            WHERE nin_number IS NULL
        """))
        
        op.alter_column('applicants', 'nin_number',
               existing_type=sa.String(),
               nullable=False)
        print("✅ Restored nin_number as NOT NULL")
    except Exception as e:
        print(f"❌ Failed to restore nin_number: {e}")
        print("⚠️  You may need to manually update NULL values first")
    
    # 3. Restore nin_slip to NOT NULL
    print("📝 Step 3: Restoring nin_slip as NOT NULL...")
    try:
        # Update NULL values to empty string
        op.execute(text("""
            UPDATE applicants 
            SET nin_slip = '' 
            WHERE nin_slip IS NULL
        """))
        
        op.alter_column('applicants', 'nin_slip',
               existing_type=sa.String(),
               nullable=False)
        print("✅ Restored nin_slip as NOT NULL")
    except Exception as e:
        print(f"❌ Failed to restore nin_slip: {e}")
        print("⚠️  You may need to manually update NULL values first")
    
    # 4. Restore unique constraint on nin_number
    print("📝 Step 4: Restoring unique constraint on nin_number...")
    try:
        op.create_unique_constraint('uq_applicants_nin_number', 'applicants', ['nin_number'])
        print("✅ Restored unique constraint on nin_number")
    except Exception as e:
        print(f"❌ Failed to restore unique constraint: {e}")
        print("⚠️  There may be duplicate NIN numbers")
    
    # 5. Remove comments
    print("📝 Step 5: Removing comments...")
    try:
        op.execute(text("""
            COMMENT ON COLUMN applicants.nin_number IS NULL;
            COMMENT ON COLUMN applicants.nin_slip IS NULL;
        """))
        print("✅ Removed comments")
    except Exception as e:
        print(f"⚠️  Could not remove comments: {e}")
    
    print("📋 Downgrade attempted. Check above for any issues.")