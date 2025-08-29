# alembic/versions/0ebd7cc64f4e_add_is_verified_is_active_to_admin.py
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0ebd7cc64f4e'
down_revision = 'cdab45db7fd0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # First set default values for existing NULL records
    op.execute("UPDATE admins SET is_verified = false WHERE is_verified IS NULL")
    op.execute("UPDATE admins SET is_active = false WHERE is_active IS NULL")
    op.execute("UPDATE admins SET is_superuser = false WHERE is_superuser IS NULL")
    
    # Now alter the columns to be NOT NULL
    op.alter_column('admins', 'is_verified',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('admins', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('admins', 'is_superuser',
               existing_type=sa.BOOLEAN(),
               nullable=False)


def downgrade() -> None:
    # Revert back to nullable
    op.alter_column('admins', 'is_superuser',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.alter_column('admins', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.alter_column('admins', 'is_verified',
               existing_type=sa.BOOLEAN(),
               nullable=True)