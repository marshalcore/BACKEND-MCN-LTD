"""add_hashed_password_to_admins

Revision ID: add_hashed_password_to_admins
Revises: e06fbddb7120
Create Date: 2026-01-18 02:17:25.034369

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_hashed_password_to_admins'
down_revision: Union[str, Sequence[str], None] = 'e06fbddb7120'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check if 'password' column exists and rename it to 'hashed_password'
    conn = op.get_bind()
    
    # Check columns in admins table
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('admins')]
    
    if 'password' in columns:
        # Rename password to hashed_password
        op.execute('ALTER TABLE admins RENAME COLUMN password TO hashed_password')
        print("✓ Renamed 'password' column to 'hashed_password'")
    elif 'hashed_password' not in columns:
        # Add hashed_password column if it doesn't exist
        op.add_column('admins', sa.Column('hashed_password', sa.String(), nullable=True))
        
        # Set a default password for existing admins
        op.execute("UPDATE admins SET hashed_password = '$2b$12$DEFAULT_HASHED_PASSWORD_FOR_RESET' WHERE hashed_password IS NULL")
        
        # Make it not nullable
        op.alter_column('admins', 'hashed_password', nullable=False)
        print("✓ Added 'hashed_password' column to admins table")


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('admins')]
    
    if 'hashed_password' in columns:
        # Check if we previously renamed from 'password'
        if 'password' not in columns:
            # Rename back to password
            op.execute('ALTER TABLE admins RENAME COLUMN hashed_password TO password')
            print("✓ Renamed 'hashed_password' column back to 'password'")
        else:
            # Drop the hashed_password column since password exists
            op.drop_column('admins', 'hashed_password')
            print("✓ Dropped 'hashed_password' column from admins table")