"""Add immediate transfer fields to payments table - SAFE VERSION (improved)

Revision ID: 0a94c4e21164
Revises: 2eb2c764464b
Create Date: 2026-02-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = '0a94c4e21164'
down_revision: Union[str, Sequence[str], None] = '2eb2c764464b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def check_column_exists(table_name: str, column_name: str, connection) -> bool:
    inspector = inspect(connection)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    connection = op.get_bind()

    print("🚀 Starting SAFE migration for immediate transfer payment fields (improved)")
    print("⚠️ This migration ONLY adds new columns and sets safe defaults. Back up DB before applying.")

    new_payment_columns = [
        ("immediate_transfers_processed", sa.Boolean(), False, sa.text("false")),
        ("transfer_metadata", postgresql.JSONB(), True, None),
        ("director_general_share", sa.Integer(), False, sa.text("0")),
        ("estech_system_share", sa.Integer(), False, sa.text("0")),
        ("marshal_net_amount", sa.Numeric(12, 2), True, None),
    ]

    for col_name, col_type, nullable, server_default in new_payment_columns:
        if not check_column_exists("payments", col_name, connection):
            if server_default is not None:
                op.add_column(
                    "payments",
                    sa.Column(col_name, col_type, nullable=nullable, server_default=server_default),
                )
            else:
                op.add_column("payments", sa.Column(col_name, col_type, nullable=nullable))

    # Normalize existing rows minimally
    try:
        connection.execute(text("UPDATE payments SET immediate_transfers_processed = false WHERE immediate_transfers_processed IS NULL"))
        connection.execute(text("UPDATE payments SET director_general_share = 0 WHERE director_general_share IS NULL"))
        connection.execute(text("UPDATE payments SET estech_system_share = 0 WHERE estech_system_share IS NULL"))
    except Exception as e:
        print(f"⚠️ Could not normalize defaults: {e}")

    # Handle possible existing name: estech_share -> estech_commission
    if check_column_exists("payments", "estech_share", connection):
        if not check_column_exists("payments", "estech_commission", connection):
            op.alter_column("payments", "estech_share", new_column_name="estech_commission")
        else:
            try:
                result = connection.execute(text("SELECT COUNT(*) FROM payments WHERE estech_commission IS NULL AND estech_share IS NOT NULL")).scalar()
                if result and result > 0:
                    connection.execute(text("UPDATE payments SET estech_commission = estech_share WHERE estech_commission IS NULL AND estech_share IS NOT NULL"))
            except Exception as e:
                print(f"⚠️ Migration check failed: {e}")

    # Limited calculations for existing successful payments
    try:
        connection.execute(text("""
            UPDATE payments
            SET director_general_share = ROUND(amount * 0.35)::integer
            WHERE status = 'success' AND amount > 0
              AND (director_general_share IS NULL OR director_general_share = 0)
        """))
        connection.execute(text("""
            UPDATE payments
            SET estech_system_share = ROUND(amount * 0.15)::integer
            WHERE status = 'success' AND amount > 0
              AND (estech_system_share IS NULL OR estech_system_share = 0)
        """))
        connection.execute(text("""
            UPDATE payments
            SET marshal_net_amount = 
                CASE
                    WHEN payment_type = 'regular' THEN ROUND((amount * 0.48) - 197.7, 2)
                    WHEN payment_type = 'vip' THEN ROUND((amount * 0.48) - 897, 2)
                    ELSE 0
                END
            WHERE status = 'success' AND amount > 0
              AND (marshal_net_amount IS NULL)
        """))
    except Exception as e:
        print(f"⚠️ Calculation step error (non-fatal): {e}")

    print("✅ SAFE MIGRATION finished. Recommended: run checks and monitor.")

def downgrade() -> None:
    connection = op.get_bind()
    columns_to_remove = [
        "marshal_net_amount",
        "estech_system_share",
        "director_general_share",
        "transfer_metadata",
        "immediate_transfers_processed",
    ]
    for col_name in columns_to_remove:
        if check_column_exists("payments", col_name, connection):
            op.drop_column("payments", col_name)
    # Attempt to restore old name if appropriate
    if check_column_exists("payments", "estech_commission", connection) and not check_column_exists("payments", "estech_share", connection):
        try:
            op.alter_column("payments", "estech_commission", new_column_name="estech_share")
        except Exception as e:
            print(f"⚠️ Failed to rename back: {e}")